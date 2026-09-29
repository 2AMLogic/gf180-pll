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
line, not this README, as the source of truth if the two ever drift.

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

(`uvx --from 'klayout-tools==0.6.0' klt --version` answers the same question in
one line, but this script needs `klt` on `PATH`, so the venv above is what to
render or `--check` through.)

**`run-signoff.sh` enforces that match now rather than asking you to make it**
(issue #630). It reads the pin out of the workflow step named above -- never
restating it, so a pin bump needs no edit in the script -- and refuses to
render or `--check` anything unless `klt --version` prints exactly
`klt <pin>`, exiting 2 with both versions named and the escape hatch above
quoted. Until it did, the mismatch surfaced as a **false `--check` failure**:
an off-pin `klt` re-renders a current `tier-report.json` differently in the
`build` block alone, and the script blamed the committed report ("is stale")
rather than the tool that had moved. Both halves are driven against a stub
`klt` by `signoff/tests/test_run_signoff.py` -- the pinned release accepted, a
`+g<sha>` source build rejected with the new message -- so the check is
exercised where it fails as well as where it passes.

For the residual case the version check cannot catch -- two klt builds that
report the same version but differ in `git_commit`, `dirty`, or
`grading_ruleset_id` -- `--check` now adds a line saying that the report's own
`build` block is the only top-level key that moved and that no T1 verdict
changed, so "stale" is not read as a verdict having shifted when it has not.

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

**1. The artifact exists, but not as a citable `klt` JSON envelope.**
~~There is no `klt` `--format json` envelope of any kind committed anywhere in
this repository. The layout evidence under `layout/evidence/*/` is the foundry
runset's own stdout plus `.lyrdb`/`.lvsdb` databases;~~ — **corrected
(2026-09-29, issue #654):** that was false from PR #587 (2026-09-26) onward, and
contradicted case 2's own correction below. Four `klt erc --format json`
envelopes are committed:
`layout/evidence/vco-layout/erc-report.json`,
`layout/evidence/pfd-cp-layout/erc-report.json`,
`layout/evidence/divider-chain-layout/erc-report.json` and
`layout/evidence/lock-detector-layout/erc-report.json`. None is cited in
`signoff/block-manifest.json` (`"evidence": {}`), each covers one sub-block
rather than the block, and item 11 additionally needs a paired `klt lvs`
envelope with `ties[]`, which does not exist. No `klt drc`, `klt lvs`,
`klt sim` or `klt pex` envelope exists, which is what makes items 3, 4, 5 and 6
uncitable. Apart from those four reports, `layout/evidence/*/` holds the
foundry runset's own stdout plus `.lyrdb`/`.lvsdb` databases; the `sim/`
campaigns recorded in
`sim/CHARACTERIZATION.md` are this repo's own Markdown-plus-raw-log record
format, produced by `sim/run_corners.py`, not by `klt sim`. `klt signoff`
grades envelopes, so none of it is citable as it stands. This affects items 3,
4, 5 and 6 most directly. Item 6 also carries a further, independent gap on
top of the envelope question — its evidence is currently unreachable on the
pinned install regardless of format — see "Item 6: statistical evidence
(`klt yield`) and the pinned-install gap" below.

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

## Item 6: statistical evidence (`klt yield`) and the pinned-install gap

Item 6's own text (`signoff/tier-report.json`, both partition rows, read
against klt 0.6.0's bundled `docs/design-evidence-tiers.md`,
`source_doc_content_hash:
sha256:63eeec72e3d849761cf32dcf091af5728b069b1515e32bb3138e9454303671e5`):

> …Where it does apply, MC runs need a recorded seed, sample count, a
> deterministic negative control, and results combined with (not instead of)
> process corners (#344). A `klt yield` JSON report — a yield estimate with
> its confidence interval, sample-size verdict, and Cpk/sigma-to-spec against
> the row's own limits — is the machine-checkable evidence for this item
> (`klt signoff`'s tier-verdict mode grades it the same way it grades the
> deterministic items above).

That is a second, independent requirement layered on top of the four
sub-criteria (seed, sample count, negative control, corner combination)
`#127`'s item-6 text already assesses: a `klt yield` JSON envelope citing a
yield estimate, its confidence interval, a sample-size verdict, and
Cpk/sigma-to-spec against the *row's own limits*. This section names that
requirement the way "Item 11 under the klt 0.6.0 checklist" above names item
11's structural gap. It does not restate or revisit `#127`'s four-criteria
assessment, and it does not move `#127`'s item-6 checkbox (#594).

**Unreachable on the pinned install, regardless of citation.** `klt yield`'s
statistics run in a separately built `klt_yield_native` Rust extension that
is not published as a prebuilt wheel and is therefore unreachable from a
single-package `pip install`/`uv tool install` — including its git-pinned
`@git+…` form — on the klt version CI pins (`klt 0.6.0`), verified on this
fleet host:

```
$ klt --help | grep -A1 '^ *yield'
    yield               Monte Carlo sample set + spec limits -> yield estimate
                        with CIs (needs a separately built Rust extension)
$ .../klayout-tools/bin/python -c "import klt_yield_native"
ModuleNotFoundError: No module named 'klt_yield_native'
```

Filed upstream and **open**: **klayout-tools#2531** ("Friction:
`klt_yield_native` still has no prebuilt wheel after two closed friction
reports asking for one") — filed from other work, not from this repository,
and cited here rather than re-filed, per this repository's friction protocol.
Two related, closed friction reports already record the consequence for this
item specifically: **klayout-tools#2466** ("`klt yield`'s native extension is
unreachable from every published release, so `klt signoff`'s kind-restricted
T1 item 6 is ungradeable for a release-pinning consumer") and
**klayout-tools#1061** (the same gap for the git-pinned install method). Host
policy forbids agents on this fleet from changing host-wide tool installs, so
building the extension locally is not a route open to this repository's own
agents — klayout-tools#2531 is the blocker's tracking issue, and closing it is upstream's
work, not this repository's.

**Which spec rows are statistical, named explicitly.** The checklist's
converse obligation is that a block whose spec has no statistical row must
say so explicitly rather than omit the item; this block's spec *does* have
statistical rows, so the obligation here is to name which ones, since
`spec/pll.md` does not itself mark any row as statistical — the set below is
assembled from where each row is actually checked, not from spec annotation,
and is not a spec change:

- **The up/down mismatch budget, terms 1–4**
  (`design/README.md#up-down-mismatch-budget`): DC UP/DN current mismatch,
  effective UP/DN switching-time skew (and its mid-window sub-case), residual
  net charge per reference cycle, and the resulting static phase offset.
  Checked against `|mean| + 3σ` at the worst corner by `sim/mc-cp-mismatch`'s
  Monte Carlo campaign (#15), most recently
  `sim/mc-cp-mismatch/records/20260927-102154-d004d5b.md` (#597) — recorded
  seed count n = 100/corner over **21 corners**: nominal plus all 20 vertices
  of the process × temperature × supply box, so every MOS bundle appears at
  both temperature and both supply extremes. That record supersedes
  `20260923-095854-1655e11.md`, which carried the same n over a 3-point
  diagonal subset; three of the four terms' binding corner moved to a point
  the subset did not contain, two of them onto a newly added mixed bundle, so
  the corner-combination sub-criterion is now satisfied by coverage rather
  than by a subset argument. All four terms still PASS. ~~`sw_stat_mismatch =
  0` decks are the systematic-only negative control, and #597's record re-ran
  that control at `fs`/125 °C/2.97 V, a bundle no earlier record of this
  campaign visited.~~ — **corrected (#602):** an *available* deck, or a
  manual re-check of one at however many corners, is not a control. The
  committed control is `sim/mc-cp-mismatch/records/20260927-093235-b994116.md`
  and its `corners/20260927-093235-b994116/negative_control.csv`; see "Item
  6(c)" below.
- **The VCO band-select mirror mismatch** (`sim/vco-tuning-range`,
  #146/#482/#597/#622): device-level Monte Carlo at nominal PVT, N = 25/band at the
  two cascade extremes (`sim/vco-tuning-range/records/20260817-143524-0e9cfc9.md`);
  band 0's own-corner closure at N = 100
  (`sim/vco-tuning-range/records/20260923-084925-1655e11.md`, #482);
  `sim/vco-tuning-range/records/20260927-081930-d004d5b.md` (#597), the first
  record here to draw **two band codes from one mismatch draw** — both sides of
  the B0→B1 adjacent pair in one netlist parse, so the coverage-hole inequality
  is measured as a per-draw ratio (1.28193 at its own one-sided 3σ tail against
  a 1.0 floor, N = 200) instead of proxied by one band's relative dispersion;
  and `sim/vco-tuning-range/records/20260927-220631-546a397.md` (#622), which
  widens that joint draw from **one point to an 11-point grid** — N = 200 per
  point, 2200 draws — spanning **all five MOS bundles**, all four vertices of
  the temperature × supply box at the thinnest bundle, and four of the seven
  adjacent pairs. All 11 points PASS; the binding point is `ss`/125 °C/3.63 V
  on **B3→B4** at 1.13935, not the B0→B1 pair the campaign had sampled until
  then.
  The two earliest records' percentage-of-mean proxy is retired by the joint
  draw: the pair's two frequencies are strongly correlated, so the
  independent-draw treatment those records were limited to double-counts
  common-mode dispersion — on #622's grid that treatment would have failed
  10 of the 11 points the joint statistic passes.
  **Two findings the single-point predecessor could not have produced**, both
  derived in the record from its own committed `per_point.csv` rather than
  asserted: (i) mismatch did **not** move the binding point off the
  deterministically thinnest corner — previously an assumption, now a
  measurement over 11 points; and (ii) ρ is a property of the **band pair**,
  not of the corner. Holding the pair at B3→B4 and varying bundle, temperature
  and supply moves ρ only over 0.8874–0.8996 (width 0.0122), while holding the
  corner fixed and varying the pair moves it over 0.8921–0.9958 (width 0.1037,
  8.5× wider). That matters because less common-mode cancellation eats more
  margin: the B3→B4 points keep ~42–56 % of their systematic overlap margin
  against ~88 % at B0→B1, which is why the binding pair moved and why the
  pre-#622 campaign was reading this claim at its most favourable pair.
  All four sample records discharge the
  negative-control sub-criterion by *citation* to `sim/mc-cp-mismatch` ("Not
  re-derived here"); the campaign's own committed control is
  `sim/vco-tuning-range/records/20260927-214737-546a397.md` (#602, widened by
  #622), covering all **25** (corner, temperature, supply, Vctrl, band) points
  the four sample records draw at — the three the earlier control covered plus
  the 11-point grid decomposed into its single-band ends — 75/75 legs PASS.
- **The random period-jitter bound** (`spec/pll.md`'s period-jitter row,
  [DR-032](../spec/decision-records/DR-032-random-period-jitter-bounded-over-the-grid.md)) —
  new since DR-032 superseded DR-020 Decision 1 and DR-023 Decision 2's "not
  obtainable on this toolchain" finding.

  **This third row is statistical in kind but not in evidence shape, and that
  distinction matters here.** The first two rows are genuine Monte Carlo
  campaigns: repeated, seeded per-device-mismatch samples read out as a
  scalar per `(corner, seed)` — exactly what a `klt yield` sample-set
  document's `measurements[].samples` array is shaped to carry.
  `sim/period-jitter/random-bound/` is not that: it is a deterministic
  noise-injection/ISF bound computed once per corner (each committed
  `results/*.json` holds one corner's per-device power-spectral-density and
  ISF-integral quantities, with no `seed` field and nothing sampled), not a
  population of repeated stochastic trials. DR-032 says as much itself — "No
  *estimate* of the random half exists… the bound does not need [the ISF
  route's ingredients]." A bound derived this way has no sample array for
  `klt yield` to consume regardless of the extension: it is a different
  *evidence shape* than item 6's clause anticipates, not merely an unreached
  one. Recorded here so the gap this row carries is not read as "the same
  problem, times three" when it is a narrower one for two of the three rows
  and a shape mismatch for the third.

### Item 6(c), the negative control: which form this repository scores, and which rows have it

Item 6's text names four sub-criteria — recorded seed, sample count,
deterministic negative control, combined with (not instead of) process
corners. Its middle clause, "deterministic negative control", does not say
whether a control *described in a record* counts or whether it must be a
*committed artifact*. This repository scores the **committed-artifact form**,
and this section is where that reading is written down, because a checklist
sub-criterion nobody has had to adjudicate is one that will be adjudicated
differently by the next two readers.

The reason is not a preference between two equally good shapes. It is
`CLAUDE.md`'s founding rule — *"Verification is the product: no claim without
a testbench"* — and item 9 of this same checklist, *"every claimed
measurement's testbench committed, documented cold-start invocation"*. A
manual invocation whose result survives only as a sentence is precisely the
form those two rules exist to exclude: it cannot be re-run, cannot be
regressed, and its failure mode is silence. A control is a claim about the
campaign, so it is held to the campaign's own standard.

**Concretely, a control scores here when** (a) its runs are produced by a
committed stage of the campaign's own runner, against the campaign's own deck
and readout, (b) its measurements are committed alongside the samples they
validate, and (c) the verdict is *derived* from those committed bytes rather
than asserted in the record's prose — so a reader, or CI, can re-check it
without a simulator. `sim/README.md`'s "Statistical convention" field
describes the shape and `sim/lib/simenv.sh` implements it.

**Where each of the three statistical rows above stands today**, readable from
this table without following a citation into a third record's prose:

| Statistical row | Control | Where the bytes are | Re-check from committed bytes |
|---|---|---|---|
| Up/down mismatch budget, terms 1–4 (`sim/mc-cp-mismatch`) | **Committed** (#602) — `repeat`/`vary`/`gate`, all 4 sub-campaigns × all 3 sampled corners, 36/36 legs PASS | `sim/mc-cp-mismatch/corners/20260927-093235-b994116/negative_control.csv` + 60 raw logs; record `…/records/20260927-093235-b994116.md` | `sim/mc-cp-mismatch/testbench/run.sh --recheck-control 20260927-093235-b994116` |
| VCO band-select mirror mismatch (`sim/vco-tuning-range`) | **Committed** (#602, widened #622) — same three legs, at all 25 (corner, temperature, supply, Vctrl, band) points its four Monte Carlo records sample, 75/75 legs PASS | `sim/vco-tuning-range/corners/20260927-214737-546a397/negative_control.csv` + 125 raw logs; record `…/records/20260927-214737-546a397.md` | `sim/vco-tuning-range/testbench/run_mismatch.sh --recheck-control 20260927-214737-546a397` |
| Random period-jitter bound (`sim/period-jitter/random-bound`) | **Committed, and it always was** — a noiseless `floor` leg measured in the same deck as each point's noisy run, in all 45 committed per-point results | the `floor` object of each `sim/period-jitter/random-bound/results/transient_<point>.json` | read `floor.sigma_s` against `noisy.sigma_s` in the same file (no runner flag needed) |

Two things about that third row, both re-derived from the committed JSONs
rather than quoted: the floor leg is present at **45 of 45** points, and the
noisy-to-floor σ ratio spans **848.6×** (`ff_-40c_3.63v`) to **6632.2×**
(`fs_27c_2.97v`) — i.e. the noiseless reference's own period spread is three
to four orders of magnitude below the quantity the bound reports, at every
point. Its `validate` stage, which additionally re-runs a same-seed repeat,
has been run at **one** point (`results/validate_typical_27c_3.30v.json`), not
all 45; the per-point `floor` leg is what carries this row, and it needs no
flag to re-read.

**What this section does not do.** It does not move item 6's checkbox — but as
of #622 the reason has changed, and the change is worth stating exactly because
this paragraph has been corrected once already. **Sub-criterion (d), corner
combination, is now met on all three rows.** `sim/mc-cp-mismatch` samples
**21 of the 45** mandated PVT points (nominal plus all 20 vertices of the
process × temperature × supply box), which the statistical-rows bullet above
records as satisfying (d) by coverage rather than by a subset argument;
`sim/period-jitter/random-bound` samples all 45. `sim/vco-tuning-range` samples
**8 of the 45** — the five MOS bundles at 125 °C/3.63 V plus `ss` at the other
three vertices of the temperature × supply box — up from the **2** it visited
before #622, and the specific gap that issue named (three of the five MOS
bundles never drawn) is closed.

Eight is a *subset*, not coverage, so unlike `sim/mc-cp-mismatch` this row rests
on a subset argument — and the distinction that makes it a sound one is that the
subset is now **tested rather than assumed**. The pre-#622 single-point campaign
asserted that the deterministically thinnest corner is also where the dispersion
binds; #622's grid measured that ordering at 11 points and found it holds (the
binding point did not move), while also finding that ρ tracks the band pair
rather than the corner — which moved the binding *pair* from B0→B1 to B3→B4.
Both findings are derived in the record from its committed `per_point.csv`, not
argued in prose. The residual this row still carries is named in that record's
own "What is still not measured" field: the grid is a union of three
one-dimensional cuts, not the full 5 bundles × 4 vertices × 7 pairs cross
product, so an interaction appearing off all three cuts is unsampled.

**What still blocks item 6 is therefore not (d).** It is the `klt yield` JSON
envelope requirement and its pinned-install gap — see "Item 6: statistical
evidence (`klt yield`) and the pinned-install gap" above, and
**klayout-tools#2531**, which is open and not actionable from this repository.
Nor does this section change any measured
number: the two control records re-measure nothing and supersede nothing, and
both campaigns' sample records keep their bytes and their verdicts. A campaign
minted before #602 has no `negative_control.csv`, and `--recheck-control` says
so rather than inventing one.

*(Correction, 2026-09-27: this paragraph read* ~~"`sim/mc-cp-mismatch` samples 3
of the 45 mandated PVT points … tracked as `#597`"~~ *— written before #602's PR
was rebased onto #597's widened axis, and left standing when it merged. Both
halves were false on `main`: the campaign was at 21 points, and #597 had closed,
so the gap was described as tracked by the very issue that had closed it.
`#127`'s derivation pass found it;
`docs/lib/check-issue-reference-state.sh` did not, because its rule-3 phrase
list had "tracked at" and "tracked by" but not "tracked as" — now fixed, so this
class of stale owner fails CI here.)*

**The sample-set export: deferred, not done — and here is exactly why.** `klt
yield`'s sample-set schema (`measurements[]`, each entry
`{name, samples, limits, …}`) is parsed entirely on the Python side, ahead of
any call into the native extension — confirmed on this host by feeding the
pinned `klt yield` a syntactically valid, minimal sample-set document: it
clears the "neither a `klt sim` report … nor a sample-set document" check and
fails one step later, at the extension call itself:

```
$ klt yield /tmp/test_sample_set.json --format json
{
  "schema_version": 1,
  "error": {
    "command": "yield",
    "message": "the klt_yield_native extension is not installed -- ..."
  }
}
```

So *producing a well-formed sample-set document* is reachable without the
extension, exactly as the issue that prompted this section observes — the
remaining work is not blocked on the wheel. What is **not** reachable without
the extension is verifying that the document says the *right* thing. Two of
the three rows above have raw per-sample CSVs that could seed a
`measurements[]` entry: `sim/mc-cp-mismatch`'s `mc_cp_dc.csv` (term 1),
`mc_cp_switch.csv` (term 2), and `mc_pfd_cp.csv` (terms 3 and 4) for the
up/down mismatch budget — the same campaign directory's `mc_dff_ctq.csv`
holds the divider-retiming flop's own clk→Q mismatch samples, a related but
separately-tracked figure that `design/README.md` deliberately keeps out of
the four-term table — and `sim/vco-tuning-range`'s four band-select-mismatch
`mismatch.csv` records for the VCO row, the largest of which (#622's 11-point
grid) also commits a derived `per_point.csv` beside its raw per-draw rows. The third row, the period-jitter
random bound, has none, per the shape mismatch above. But the committed statistic for, e.g., term 1 is not "every row of
`mc_cp_dc.csv`" — it is the worst-corner, worst-Vctrl-point, signed
`|mean| + 3σ` figure that `sim/mc-cp-mismatch/testbench/run.sh`'s own
worst-point-selection logic derives (the same logic issue #487 corrected
once already, from a folded to a signed statistic, after the folded form was
found to read about 1.3× optimistic on the same 300 samples). A
`measurements[]` entry built by flattening the CSV without reproducing that
selection would silently misstate the very quantity `design/README.md`'s
budget table checks each term against — and there is no way to catch that
mistake locally: unlike the schema check above, `klt yield` cannot run its
own statistics here to reveal a *wrong* sample set, only a malformed one.
Committing an unverifiable derivation is the citation-that-merely-grades trap
**klayout-tools#2467** already names for the verdict side (`klt signoff`
grades a yield citation on status alone, so an undersized or mis-derived
campaign can render `met`), applied here to the input side instead: an
export nobody can validate is not evidence that would survive being read, it
is a citation waiting to be trusted. **This is deferred**, to whoever
next has a built `klt_yield_native` and can validate a candidate export
against `sim/mc-cp-mismatch`'s and `sim/vco-tuning-range`'s own committed
figures before trusting it. At that point the two exportable rows above, and
`run.sh`'s existing worst-point-selection logic, are the starting material;
the period-jitter random bound is out of scope for this particular artifact
regardless of tooling, for the reason stated above.

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
- **klayout-tools#2531** (open) — `klt_yield_native`, the Rust extension
  `klt yield` needs, has no prebuilt wheel, so item 6's evidence
  (`klt yield` JSON reports) cannot be produced from this repository's pinned
  install; see "Item 6: statistical evidence (`klt yield`) and the
  pinned-install gap" above. Unlike the three issues above, **this one was
  not filed from this repository's own work** — it predates issue #594 and
  was filed from other work — and is cited here rather than duplicated, per
  issue #594.
