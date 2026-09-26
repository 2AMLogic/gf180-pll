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
| ~~`design-evidence-tiers.md`~~ | ~~A pinned copy of `klayout-tools`' T1 checklist. See "Why the checklist is vendored here".~~ — **removed (2026-09-26, issue #564):** klt 0.6.0 bundles the eleven-item checklist, which was this file's own stated deletion condition. See "Which checklist this is graded against". |
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

**Match the *full* version string, suffix included -- a source build of the
pinned version is not the pinned version.** 0.6.0 records its own build
provenance in the report (`build.version`, `git_commit`, `git_tag`,
`is_release`, `grading_ruleset_id`), and those fields differ between the
released PyPI wheel and a locally source-built tree at the same release number,
so a report rendered by the latter fails CI's `--check` on the provenance block
alone. A source build reports a PEP 440 local-version suffix --
`klt 0.6.0+gef984d3414d4`, `is_release: false`, `git_tag: null` -- where the
released wheel reports exactly `klt 0.6.0`. **`klt --version` is the only
reliable discriminator**: `pip show klayout-tools` prints a bare `0.6.0` with
`INSTALLER: pip` for *both*, and a source build installed into `~/.local/bin`
can shadow the wheel on `PATH`. If your `klt --version` carries a `+g<sha>`
suffix, render in a clean environment that has the release instead:

```sh
python3 -m venv /tmp/klt-pinned
/tmp/klt-pinned/bin/pip install 'klayout-tools==0.6.0'
/tmp/klt-pinned/bin/klt --version          # must print exactly: klt 0.6.0
PATH=/tmp/klt-pinned/bin:$PATH bash signoff/run-signoff.sh
```

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
from. ~~Item 11 (power delivery, structural) needs a `klt erc` supply spec and
report; this repo has neither — that gap is tracked separately as #427.~~ —
**corrected (2026-09-26, issue #564):** ~~item 11 (power delivery, structural)
needs a `klt erc` supply-spec run *and* a `klt lvs` envelope. A supply spec and
report exist for one sub-block, `vco_block`, and have been committed since
2026-09-20 (`layout/evidence/vco-layout/erc-supply-spec.json` and
`erc-report.json`, PR #434, which closed #427). They are not cited here: they
cover one sub-block rather than the block, no `klt lvs` envelope exists to
pair them with, and they would not grade `met` even if both of those were
fixed (see "Item 11 under the klt 0.6.0 checklist" below). The remaining
item-11 gap was filed as #565 (then open).~~ — **corrected (2026-09-26, issue
#588):** PR #587 closed #565: every real block (`vco_block`, `pfd_cp`,
`divider_chain`, `lock_detector`) now has a committed `klt erc` supply spec
and report, produced on the klt version CI pins (see "Item 11 under the klt
0.6.0 checklist" below for what each one renders). None of the four is cited
in `signoff/block-manifest.json`, so none of it changes today's verdict, and
citing the clean ones would not be enough on its own either: item 11 grades a
*set*, a `klt erc` supply citation paired with a `klt lvs` citation, and no
`klt lvs` envelope exists for any block — the same "not a `klt` envelope" gap
point 1 above names for items 3, 4, 5 and 6. No open issue in this repository
tracks producing that envelope; the remaining item-11 gap is unowned.

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

## Which checklist this is graded against

**Corrected (2026-09-26, issue #564).** `run-signoff.sh` no longer passes
`--tiers-doc`. It grades against the checklist bundled inside the pinned `klt`
release itself — klt 0.6.0, whose bundled `docs/design-evidence-tiers.md`
carries all eleven T1 items — and the vendored bridge copy that used to live in
this directory has been deleted, exactly as its own stated deletion condition
("once a released `klt` bundles an eleven-item checklist") required. The
report's `source_doc` now reads `docs/design-evidence-tiers.md` and its
`source_doc_content_hash` is the bundled file's hash,
`sha256:63eeec72e3d849761cf32dcf091af5728b069b1515e32bb3138e9454303671e5`.

That also closes the bridge's first stated limit (below, struck). Because the
report pins the bundled checklist's hash, a future `klt` pin bump that ships an
amended checklist re-renders a different report and fails CI's `--check` until
someone re-renders it — so an upstream amendment can no longer arrive silently
through the pin. **No separate re-hash guard was added**, because there is no
longer a vendored copy for one to guard. What this does *not* do: the
`--check` failure only says the report changed; re-reading the checklist diff
at that moment is still a deliberate act, as the next section is.

The re-render against the bundled checklist changed four lines of
`tier-report.json` and no verdict: `source_doc`, `source_doc_content_hash`, and
item 11's `notes` entry on each of its two partition rows (its `text`
is unchanged). All 22 T1 rows are still
`unmet` / `no_evidence`, and all 22 still read `graded_by_build: true`.

### Item 11 under the klt 0.6.0 checklist

The vendored copy had fallen behind the klt 0.6.0 bundle by three unified-diff
hunks (`diff -u signoff/design-evidence-tiers.md` against the installed
wheel's `klayout_tools/data/design-evidence-tiers.md`):

1. **Mixed-signal partition boundary** — a new, optional manifest field,
   `partition_boundary` (klayout-tools#2278), which the report echoes onto
   every row of the partition it names. It is reported, not graded. This
   repo's manifest does not declare it yet; the boundary is stated in prose in
   "Block kind" above.
2. **Item 11, power delivery** — the substantive change, read below.
3. **Staleness** — every citation now reports `input_verified: true | false |
   null` (klayout-tools#2196): whether `klt signoff` re-hashed the artifact
   itself rather than only comparing the envelope's self-reported hash. Never
   graded on. This manifest cites nothing, so no row carries it.

~~Item 11's notes gained, among other things, two rules that bear on the only
item-11 evidence this repository has — the `vco_block` supply spec and report
under `layout/evidence/vco-layout/` (see "Why every row is `unmet`"). Neither
is cited, so neither changes today's verdict; this is what they would render
if they were. The ERC half was checked by calling klt 0.6.0's own item-11
supply-spec grader (`klayout_tools.signoff._resolve_erc_supply_spec`) on the
committed report and spec directly. A full manifest run cannot reach that code
path here: item 11 also requires a `klt lvs` envelope, none exists, and the
grader returns `wrong_kind` for a set without one before it reads the ERC half.

- **A spec declaring no `ties[]` now renders `supply_spec_incomplete`.** The
  committed `erc-supply-spec.json` declares no `ties[]` and no
  `ties_disclosure`, and the grader returns exactly that reason for it. The
  spec's own `_ties_omitted` note gives klayout-tools#2169 (a `ties[]` bug that
  falsely merged routed supplies) as the reason for omitting them; that bug was
  fixed upstream on 2026-09-20, so the rationale no longer holds. Adding a
  `ties_disclosure` to the spec file would not change the reason on its own:
  0.6.0 reads the disclosure from the ERC *envelope's* recorded coverage, and
  the committed report was produced by a 0.5.0 build that records none. The
  route to a graded item-11 ERC half is a fresh `klt erc` run on 0.6.0 with
  `ties[]` declared, which is #565's work, not this directory's.
- **`VDD_VCO`'s second island no longer reads as a confirmed defect.** The
  report's one supply finding is `erc.unconnected_net`: `VDD_VCO` resolves to
  two islands. The new item-11 caveat (klayout-tools#2180) says a multi-island
  finding on a well-tap-strapped supply is not a confirmed power-delivery
  defect on its own, and asks for a cross-check against an independent,
  device-aware LVS extraction whose deck does not join nets by label alone
  (naming a bare `connect_implicit('*')` as the trap). That cross-check is
  already committed: `layout/evidence/vco-layout/PROOF-433-vdd-island-fix.md`
  identified this PDK deck's `connect_implicit('*')` name-join, bypassed it by
  counting geometric islands of the extracted `VDD_VCO` net's own shapes on
  every extracted layer including the n-well, and found the remaining island
  (`vtoi_core`'s bottom tap band) joined to the rest through the continuous
  n-well. Under the caveat, then, that island is a false positive of the
  metal-only model, which is what `PROOF-erc.md` already concluded. **The
  caveat is guidance for a reader, not a grading exemption:** the grader still
  returns the `VDD_VCO` finding as a supply finding, and would render
  `supply_not_continuous` for it once the `ties[]` rule above was satisfied.
  (It checks `ties[]` first, so today the finding is masked by
  `supply_spec_incomplete`.) Whether declaring `ties[]` in a 0.6.0 re-run also
  merges the second island in `klt erc`'s own model is not verified here.

Net: item 11 is `unmet` for this block for more reasons than the row's
`no_evidence` says, and none of them is a known power-delivery defect.~~ —
**corrected (2026-09-26, issue #588):** the above described `vco_block` as the
only block with item-11 evidence, and worked out what its ERC half would
render by calling the grader directly, because no fresh run existed yet. PR
#587 (issue #565) did that fresh run, on the klt version CI pins, for
`vco_block` and the three blocks that had none — `pfd_cp`, `divider_chain`,
`lock_detector`. Each block's own `PROOF-erc.md` under `layout/evidence/` is
now the record of what the grader renders for it; this section summarizes
rather than re-derives them:

- **`vco_block`** (`layout/evidence/vco-layout/PROOF-erc.md`): the `ties[]`
  rule above is now satisfied — a real declaration, not the closed-bug
  rationale this section used to describe — but `VDD_VCO` still resolves to
  two electrical islands under `klt erc`'s metal-only model, so the grader
  renders `supply_not_continuous`, unmasked. Cross-checked against an
  independent, device-aware LVS extraction as klayout-tools#2180's caveat
  requires (`PROOF-433-vdd-island-fix.md`, reused rather than re-run): the
  second island is real silicon, joined to the first through the shared
  n-well, and not a power-delivery defect — but `klt erc` has no
  well-mediated-continuity model to credit that with, so the block stays
  `unmet` for this precisely named, non-defect reason.
- **`pfd_cp`** (`layout/evidence/pfd-cp-layout/PROOF-erc.md`): the
  supply-continuity finding is clean, but the block's dual-biased well cannot
  be expressed as a single `ties[]` takeoff, so the spec discloses the
  omission (`ties_disclosure`, `kind: "tool_limitation"`) rather than
  declaring or silently omitting it. The grader renders
  `supply_spec_disclosed_tool_limitation` — an honest disclosure, still
  `unmet`. The underlying gap in `ties[]`'s well-side selector is filed
  upstream (klayout-tools#2540, klayout-tools#2541), not tracked in this
  repository.
- **`divider_chain`** and **`lock_detector`** (their own `PROOF-erc.md`
  files): both declare and check a real `ties[]` entry with zero
  `erc.missing_tie` findings, and both declared supplies resolve to exactly
  one labelled island — the ERC half's supply-continuity finding is clean for
  both.

None of the four is cited in `signoff/block-manifest.json`, so none of this
changes `tier-report.json`'s verdict today, and citing `divider_chain` and
`lock_detector` — the two blocks with no adverse ERC-half reason at all —
would not be enough on its own either: item 11 also requires a `klt lvs`
envelope, none exists for any block, and the grader returns `wrong_kind` for a
set without one before it reads the ERC half at all (see "Scope note" in each
`PROOF-erc.md`).

Net: item 11 is `unmet` for every block, for reasons that are now precisely
named per block rather than uniform, and none of them is a known
power-delivery defect. The one gap left with no open owner is the `klt lvs`
envelope itself.

### Superseded: why the checklist was vendored here

The section below is kept for its history and struck, per this repository's
convention for withdrawn claims. Every present-tense statement in it is false
as of issue #564; the correction is the section above.

~~`run-signoff.sh` passes `--tiers-doc signoff/design-evidence-tiers.md` rather
than using the checklist bundled inside the installed `klt` wheel. The released
wheel (`klayout-tools` 0.5.0, released 2026-09-15) bundles a **ten**-item
checklist; T1 item 11 landed upstream on 2026-09-17 (klayout-tools#2025). Graded
against the bundled copy this block renders 20 rows and item 11 does not exist
at all — which is exactly the silent staleness this directory is here to
prevent. (The underlying release lag is upstream's own klayout-tools#2173, not
something this repo can close.)~~ — **corrected:** CI pins klt 0.6.0, whose
bundled checklist has eleven items and renders 22 T1 rows for this block.

~~`--tiers-doc` is `klt signoff`'s own documented override for this, so the
vendored copy is a bridge, not a fork. It is a byte-for-byte copy of
`2AMLogic/klayout-tools` `docs/design-evidence-tiers.md` at commit
`428951e036935d37161732adb55915049c598cc4` ("feat(signoff): add T1 item 11,
power delivery (structural) (klayout-tools#2057)", 2026-09-19), sha256
`275964ed6cdc3ed57566710540daa76beb26c1b67fb4b3dbf598d05b640a7ce0`. It carries
no local edits and must not acquire any: the checklist is upstream's to write,
and an edit here would be this repo grading itself against its own rules.
**Delete this file and the `--tiers-doc` flag once a released `klt` bundles an
eleven-item checklist.** Editing it is caught immediately — every item's text
is copied verbatim into `tier-report.json`, so any change re-renders the report
and fails CI's `--check`.~~ — **corrected:** the copy was also stale — three
hunks behind the 0.6.0 bundle, all read above — and both it and the flag are
deleted.

Two limits of the bridge, stated rather than assumed:

- ~~Because item text is baked into the committed report, a *silent* upstream
  amendment to the checklist is not detected here — only a change to this
  pinned copy is. Re-pinning is a deliberate act, and re-reading the diff is
  part of it.~~ — **corrected:** with no pinned copy, an amended checklist
  arriving through a `klt` pin bump changes the report's
  `source_doc_content_hash` and fails `--check`.
- ~~klt 0.5.0 parses and renders item 11's row but has none of item 11's grading
  logic (its compound array-of-citations evidence entry, its `erc` /
  `place-and-route` accepted kinds). With no citation the row is `unmet` either
  way, so the verdict is correct today — but **do not cite item 11 evidence
  against 0.5.0 and read the result as graded.** Filed upstream as the friction
  issues named below.~~ — **corrected:** CI pins 0.6.0, which implements item
  11's grading, and the committed report says so mechanically: item 11 reads
  `graded_by_build: true` on both partition rows.

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
worked around silently. Their upstream state was re-checked on 2026-09-26
(issue #564); two of the three are fixed, and the committed report shows it.

- **klayout-tools#2175** — ~~the tier report names the checklist it graded
  against (`source_doc`) but does not pin its content, so a committed report
  cannot be checked against a checklist that has since changed. The grader
  demands `content_hash` pinning from every citation for exactly this reason
  and does not apply it to its own governing document.~~ — **corrected:**
  closed as completed upstream on 2026-09-20 and shipped in klt 0.6.0 as the
  report's `source_doc_content_hash`, which `tier-report.json` carries.
- **klayout-tools#2176** — ~~with `--tiers-doc`, the doc's item list and the
  build's grading logic can be at different versions, and the report says
  nothing about which items the running build actually implements. An
  ungradeable row is indistinguishable from a correctly-graded `unmet` one.~~
  — **corrected:** closed as completed upstream on 2026-09-20 and shipped in
  klt 0.6.0 as the report's `build` block, `build_t1_item_count`, and
  per-item `graded_by_build`, all of which `tier-report.json` carries.
- **klayout-tools#2177** — a manifest cannot record *why* an item is honestly
  uncited, so the machine verdict and its explanation live in two files that
  drift apart. Most of the section "Why every row is `unmet`" above is prose
  that wants to be manifest data. **Still a gap in klt 0.6.0.** The issue was
  closed upstream on 2026-09-20 as *not planned* — on a citation-accuracy
  defect in its implementation guidance, not on the merits, with a re-filed
  proposal invited — so nothing shipped. It has not been re-filed from this
  repository as of issue #564.
