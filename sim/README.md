# sim/ — evidence record format

This directory holds simulation testbenches and their results. Results are
**append-only evidence**: once a record is written, it is never edited or
deleted. A re-run — even one that corrects a mistake — mints a new record
with a new ID; a correction references the record it supersedes rather than
overwriting it in place.

This convention exists because CLAUDE.md commits this repo to two rules that
need a concrete schema to be enforceable:

- **Verification is the product.** No claim without a testbench. Every
  recorded result carries the full PVT corner matrix (−40/27/125 °C, 3.3 V
  ±10 %, process corners) unless the record explicitly states why a subset
  was used.
- **`sim/` is append-only evidence.** Re-runs get new records; records are
  never edited or deleted.

## Provenance of this convention

This format is **copied and adapted** from the sister repo
`2AMLogic/gf180-bandgap`, per CLAUDE.md's harness-bootstrap rule (copy the
sister-repo pattern rather than reinventing). Source:

- **Source file**: `sim/README.md` on `2AMLogic/gf180-bandgap` `main`
- **Source commit**: `67525f67d8152fff7575c7d13ea185db869e2870`
  ("docs: define sim/ evidence record format and append-only convention",
  bandgap #22) — the last commit to touch that file, and the convention
  ratified on bandgap `main` as of 2026-07-30 (bandgap `main` at
  `8fb0ea627569079147c91bff8e3aee658c976e54`).

**Reconciliation note.** Bandgap's harness PR (bandgap #23, branch
`feature/issue-2`) proposes a *machine-readable* evidence scheme —
`sim/results/<tb>/<UTC>-<sha>[-dirty].{json,csv}` — which does not match the
Markdown-record convention ratified in bandgap #22. That PR was **still open
and unmerged** when this file was written, so the ratified Markdown
convention above is what is copied here. If bandgap later supersedes its
convention, this repo follows **via its own `spec/` decision record** — #6 has
since landed `spec/decision-records/TEMPLATE.md`, so the mechanism now exists:
copy it to `spec/decision-records/DR-NNN-<slug>.md`. Never a silent fork. The
two schemes are not actually in conflict for us: a harness (issue #2) may emit
machine-readable `corners/<record-id>/` artifacts *in addition to* the Markdown
summary record, but the Markdown record under `records/` is the citable
evidence object and is mandatory.

Deltas from the bandgap convention are marked **[PLL delta]** below, each
with its justification. Everything unmarked is bandgap's convention verbatim
in substance.

## Directory / naming convention

Each testbench topic gets its own experiment directory:

```
sim/
  <experiment-slug>/                 # e.g. lock-time, devchar-delay
    testbench/                       # testbench netlist(s) / xschem export used
    netlist-snapshots/
      <record-id>.spice              # frozen DUT netlist used for this record
    corners/
      <record-id>/
        <corner-id>.log              # raw ngspice output per PVT point
                                      # e.g. ss_-40c_2.97v.log
    records/
      <record-id>.md                 # append-only summary record
```

- **`<experiment-slug>`** — short, descriptive, kebab-case name for what is
  being verified. One directory per distinct claim being tested, **not** per
  run. The campaigns already scoped for this block:

  | Slug | Claim under test | Issue |
  |---|---|---|
  | `devchar-delay` | delay-cell drive/delay vs. PVT | #4 → #8 |
  | `devchar-cp` | mirror output resistance / compliance | #4 → #9 |
  | `devchar-passives` | MIM vs. MOS cap, poly-resistor options | #4 → #10 |
  | `divider-ratio` | ÷2/3 cell moduli and speed margin, chain ratio over the whole N = 4–64 range, retiming setup closure | #11 |
  | `lock-detector` | phase-error window comparator: assert/deassert and window edges | #11 |
  | `vco-tuning-range` | open-loop ring VCO range, Kvco | #8 |
  | `pfd-deadzone` | PFD + charge-pump phase-to-charge transfer through zero phase error (dead-zone freedom), and the residual charge offset at zero | #9 |
  | `cp-compliance` | charge-pump output compliance range, UP/DN current and switching-time mismatch, 2-bit Icp trim range | #9 |
  | `loop-dynamics` | loop bandwidth / phase margin vs. R–C and Kvco spread | #10 |
  | `lock-time` | closed-loop lock acquisition | #12 |
  | `output-range` | closed-loop output-band coverage | #12 |
  | `period-jitter` | period jitter (deterministic + random) | #13 |
  | `supply-sensitivity` | supply pushing, quiescent/dynamic power | #14 |
  | `mc-cp-mismatch` | charge-pump mismatch distribution | #15 |

  New campaigns add rows here as they are created; the list is descriptive,
  not a closed set.

- **`<record-id>`** — unique and traceable:
  `<YYYYMMDD>-<HHMMSS>-<short-git-sha>` (e.g. `20260730-142500-3f1c9ab`),
  date and time in **UTC**, sha being this repo's `HEAD` when the run
  started. Re-runs simply mint a new `<record-id>`; nothing under `records/`
  is ever edited in place. The same `<record-id>` ties together the netlist
  snapshot, the raw per-corner logs, and the summary record for one run. If
  the tree was dirty at run time, the ID is unchanged but the record's
  **Environment provenance** field must say so (see below) — a dirty-tree
  record is not reproducible from the sha alone.

- **`<corner-id>`** — `<corner-bundle>_<temp>c_<supply>v.log`, e.g.
  `ss_-40c_2.97v.log`, `tt_27c_3.30v.log`, `ff_125c_3.63v.log`. Supply is
  always written to two decimals — **[PLL delta]**, a small tightening rather
  than bandgap verbatim: bandgap's naming line shows a one-decimal
  `tt_27c_3.3v.log` while its own worked example writes `3.30v`. Fixing the
  width at two decimals removes that inconsistency and keeps corner filenames
  sorting lexically in supply order.

  **[PLL delta]** — the corner field itself: bandgap's is a bare
  MOS process corner; here it is a *bundle name*, because gf180mcu has no
  single global corner switch — each device family carries its own `.lib`
  section in `sm141064.ngspice` (MOS `tt/ff/ss/fs/sf`, plus the independent
  `res_*`, `mimcap_*`, `moscap_*`, `bjt_*`, `diode_*` axes). A bundle name
  is lowercase alphanumeric with `-` only (**never `_`**, which stays the
  unambiguous field separator): `tt`, `ss`, `ff`, `fs`, `sf`,
  `ss-resss-mimss`, `all-slow`. Every bundle name used in a run **must** be
  expanded into its exact `.lib` section list in the record's corner-matrix
  field — the filename is a handle, the record is the definition.

  **Campaigns that sweep beyond the PVT grid.** Some campaigns sweep an
  independent variable *in addition to* process/temperature/supply — a phase
  offset, a trim code, a control voltage — so one PVT point produces several
  logs and `<corner-bundle>_<temp>c_<supply>v` is no longer unique. Such a
  campaign appends the extra variable as a further `_`-separated field, and may
  prepend a measurement-kind field when it runs more than one analysis over the
  same grid:

  ```
  [<kind>_]<corner-bundle>_<temp>c_<supply>v[_<extra>][_<extra>…].log

  ss_125c_3.30v_dphi200p.log      pfd-deadzone: phase offset (dphi) swept
  dc_ff_-40c_2.97v_code00.log     cp-compliance: DC analysis, Icp trim code
  sw_tt_27c_3.30v_vctrl1.65.log   cp-compliance: switching analysis, Vctrl
  ```

  An extra field is `<name><value>` with no separator between them, so the `_`
  boundary stays unambiguous; the value is written exactly as the deck spells
  it (SPICE suffixes included, `-` for negative). Every swept variable **must**
  be named, with its points, in the record's corner-matrix field, on the same
  terms as the PVT axes — the filename is still only a handle. The three fixed
  fields keep their meaning and position, so a campaign that sweeps nothing
  extra is unaffected: this documents a convention already in use, it does not
  change the schema.

- **`testbench/`** is not versioned per record — it holds the current
  testbench netlist(s)/xschem export(s) used to generate records. If the
  testbench itself changes in a way that could affect comparability across
  records, note that in the new record's summary (e.g. under Claim,
  Methodology, or a free-text note).

## Default corner matrix

Unless a record states otherwise, every result is swept over the full grid:

| Axis | Points |
|---|---|
| Temperature | −40 °C, 27 °C, 125 °C |
| Supply | 2.97 V, 3.30 V, 3.63 V (3.3 V ±10 %) |
| Process | MOS bundles `tt`, `ff`, `ss`, `fs`, `sf` |

That is 45 points for a MOS-only sweep. **Passive corner axes are
independent of the MOS process corners** (`res_typical/res_ff/res_ss`,
`mimcap_typical/mimcap_ff/mimcap_ss`,
`moscap_typical/moscap_ff/moscap_ss`): a sweep over MOS corners alone
silently leaves every passive at typical. That is a legitimate choice for
some claims and a fatal omission for others — the loop filter's bandwidth
and phase margin ride on the R and C skews, not the MOS skew — so **a record
that sweeps only MOS corners must say so explicitly** in its corner-matrix
field, and a loop-dynamics or loop-filter claim that does so must justify it
in its Methodology field. **[PLL delta]** bandgap notes the same hazard for
its resistor/BJT axes; this repo names the specific passive sections the loop
filter depends on.

Any subset of the default grid — fewer temperatures, one supply, MOS-only
process, a single nominal point for a Monte Carlo distribution claim — is
allowed **only** with an in-record justification. "The sim was slow" is not a
justification; "mismatch distribution is evaluated at nominal PVT, corner
sensitivity covered separately by record X" is.

## Summary record format

Each run produces one `records/<record-id>.md` file with the following
fields. Fields are mandatory unless marked optional; a field that does not
apply is written as `N/A` **with a reason**, not omitted.

- **Record ID** — the `<record-id>` for this run (matches the filename and
  the corresponding `netlist-snapshots/` / `corners/` subdirectory).

- **Claim** — what this record substantiates. Two accepted forms
  (**[PLL delta]** — bandgap admits only the first):
  1. a **spec claim** — the ratified spec parameter/line, referenced as
     `spec/<file>.md#<anchor>` (placeholder anchors until #1 ratifies a
     spec, as bandgap prescribes); or
  2. a **design-input claim** — a design question this record answers rather
     than a spec line it passes/fails, referenced by issue number and stated
     as a question (e.g. "#4 → #10: which loop-filter cap type meets the
     area budget with acceptable C–V linearity?"). Device-characterization
     records (#4) substantiate *sizing decisions* for #8/#9/#10; forcing
     them to name a spec line would either misattribute them or block them
     on #1.

  A claim of either form is still a claim: it needs the testbench, the
  corners, and the provenance.

- **Netlist provenance** — `schematic` (`design/...`) or `extracted`
  (post-layout, `layout/...`), with the path, plus the SHA-256 of the frozen
  `netlist-snapshots/<record-id>.spice`. Required so post-layout re-runs are
  distinguishable from the original schematic-level record (#18).

- **Environment provenance** — **[PLL delta]**, absorbed from #4: the
  environment must be reconstructable from the record alone.
  - PDK variant + pinned hash (e.g. volare `gf180mcuD`, open_pdks
    `c6d73a35f524070e85faff4a6a9eef49553ebc2b`)
  - model library file used (e.g. `sm141064.ngspice`)
  - simulator version (e.g. `ngspice 46`), and schematic-capture version if
    the netlist came from a schematic export (e.g. `xschem 3.4.7`)
  - this repo's git commit, **and whether the tree was dirty**
  - host OS/arch, if the result is at all sensitive to it (long transients
    and RNG-seeded analyses are)

  A record naming corner sections without naming the model library and PDK
  hash that define them is not traceable — model sections are only
  meaningful against a pinned PDK.

- **Corner matrix run** — explicit list of (corner bundle, temperature,
  supply) points actually executed, **with each bundle name expanded into
  its exact `.lib` sections**, and an explicit statement of which axes were
  *not* swept (see "Default corner matrix"). Must be the full default grid
  unless the record states why a subset was used.

- **Methodology / criteria / limitations** — **[PLL delta]**, absorbed from
  #12 and #13. The measurement criterion stated alongside the number, and
  the honest limits of the method:
  - the **measurement criterion** that turns a waveform into the reported
    scalar — e.g. the lock criterion for #12 (frequency and phase settling
    bands, the window they must hold for, cold-start vs. re-lock, the
    frequency step applied), or the measurement topology for #4 (N-stage
    test ring vs. single-stage step response)
  - simulator settings that materially affect the number (timestep/`reltol`,
    transient length, seeds, `.measure` expressions)
  - **known methodology gaps, recorded instead of papered over.** If the
    flow cannot credibly produce a number, the record says so and reports no
    number — e.g. ngspice transient-noise limits for closed-loop random
    jitter (#13). An honest gap here is a valid record; an unsupported
    number is not, and "no claim without a testbench" includes "no number
    without a method that supports it."

- **Statistical convention** (when applicable, e.g. Monte Carlo mismatch
  analysis) — N samples and sigma level reported, plus which mismatch/
  process variation model was enabled. Used for distribution claims that are
  not a per-corner pass/fail (#15).

- **Result** — per-corner pass/fail or measured value, plus an overall
  pass/fail against the ratified spec value (for a spec claim) or the
  conclusion drawn (for a design-input claim). Free-form tables are fine and
  expected here — e.g. a per-block power breakdown (#14) or a cap-type
  comparison table (#4) lives in this field.

- **Links** — paths to the testbench file(s), the frozen netlist snapshot,
  and the raw per-corner logs used to produce this record.

- **Timestamp / author** — when the record was created (UTC) and who (human
  or agent) created it.

- **Supersedes** (optional) — the prior `<record-id>` this record supersedes,
  for corrections or for a post-layout extracted re-run that reports a
  schematic-vs-extracted delta against the schematic-level record.

### Status / supersession language

Records use the same status *vocabulary* as `spec/` decision records
(`spec/decision-records/TEMPLATE.md`, landed in this repo via #6; that template
is in turn adapted from bandgap's), so the two conventions read as one:

- A record's standing is one of **`current`** or **`superseded by
  <record-id>`**. There is no `draft` or `retracted` state: a record is
  evidence of what a run produced, and a run that happened cannot become
  un-happened. Decision records add a third, **`proposed`**, which has no
  analogue here: a record is minted by a run that already completed, so it is
  never "not yet binding".
- **`Status` is not a record field — do not emit one.** The schema above is the
  complete field set, and it has no `Status`. Standing is *derived*, not
  stored: a record is `current` until some later record names it in a
  **Supersedes** field, at which point it is `superseded by` that record. The
  vocabulary exists so humans and tools can *talk* about standing
  consistently; nothing writes it into a file.
- The superseding record carries **Supersedes: `<record-id>`**; the superseded
  record is **not edited** to add a back-reference — that would be a rewrite.
  Standing is therefore found by reading *forward* from the superseded record:
  scan for the record that names it.
- **[PLL delta] — one deliberate divergence from the decision-record
  convention.** `spec/decision-records/TEMPLATE.md` supersedes a decision
  record by editing the **old** record's `Status` to `superseded by DR-NNN`, a
  forward pointer written in place. Evidence records do **not** do this: the
  pointer lives only in the *new* record's **Supersedes** field, and the
  superseded record's bytes never change after creation. The reason is that the
  two artifacts have different jobs — a decision record is a governance
  document whose current standing must be legible at a glance to anyone who
  opens it, so a controlled in-place status edit earns its keep; an evidence
  record is a frozen observation of what a simulator actually emitted, and
  editing it at all (even to add a true, helpful pointer) forfeits the
  guarantee that makes `sim/` citable. When the two rules seem to conflict,
  immutability wins here and legibility wins in `spec/`.
- Same rule as `spec/`, and the one both conventions share without
  qualification: *do not delete or rewrite a record — supersede it.*

## Append-only rule

`records/*.md` files are never edited or deleted after creation. A re-run or
a correction always creates a new record with a new `<record-id>`. If it
corrects or replaces a prior result, it references that prior record via
**Supersedes** rather than overwriting it. This applies even to typo fixes —
the append-only guarantee is what makes `sim/` usable as an evidence trail;
"fixing" an existing record in place would defeat that.

The same rule binds the raw artifacts: `corners/<record-id>/` logs and
`netlist-snapshots/<record-id>.spice` are written once and never touched
again. A tool that would rewrite them is wrong, not convenient.

Only `testbench/` and this README are mutable — and a testbench change that
affects comparability must be called out in the next record.

## Retention policy — what is kept

| Artifact | Retained? | Why |
|---|---|---|
| Summary record (`records/<id>.md`) | **Always, committed** | the citable evidence object |
| Frozen netlist snapshot (`netlist-snapshots/<id>.spice`) | **Always, committed** | the record's claim is meaningless without the exact DUT |
| Raw per-corner ngspice logs (`corners/<id>/*.log`) | **Always, committed** | the primary evidence the extracted metrics were read from; includes the warnings a summary hides |
| Extracted metrics / measurement tables | **Always** — inside the record, or as a small CSV beside the logs | machine-readable comparison across records |
| Full waveform rawfiles (`.raw`) | **No, not committed** | hundreds of MB per transient; regenerable from the frozen netlist + logged environment |
| Plots | Only when the plot *is* the argument | a plot is a rendering, not evidence; commit it with the script that generated it |

**How the tooling enforces this.** Root `.gitignore` ignores `*.raw` and `*.log`
tree-wide, which would otherwise silently swallow the corner logs this table
mandates committing — `git add sim/<slug>/corners/<id>/` would add nothing for
them and the record's **Links → Raw logs** path would point at untracked files.
A scoped negation un-ignores exactly the evidence path and nothing else:

```gitignore
*.raw
*.log
!sim/*/corners/**/*.log
```

So per-corner logs under `corners/<record-id>/` are trackable, while `.raw`
files there and stray `.log` files anywhere else (e.g. `testbench/scratch.log`)
stay ignored. Anyone adding a new committed-evidence artifact type that collides
with an ignore rule must extend that negation in the same narrow way — never by
`git add -f`, which leaves the next run's logs silently untracked again.

**Waveform rule.** When a waveform is itself the evidence — a lock
transient, a control-line ripple trace, a startup sequence — do **not**
commit the rawfile. Commit a **downsampled CSV of the specific signal(s)**
under `corners/<record-id>/` (e.g. `lock_transient_ss_-40c_2.97v.csv`),
state the decimation in the Methodology field, and keep the deck able to
regenerate the full rawfile. Anything above a few MB per record wants
justification in the record.

**Nothing is pruned.** Old records stay after they are superseded; that is
the point. If `sim/` ever becomes genuinely too large, the answer is a
decision record under `spec/` proposing an archival scheme, not a `git rm`.

## No fabricated evidence

Files under `sim/<experiment-slug>/` may only be created by an actual run of
an actual testbench. Do not commit an example, a template, or a
plausible-looking record into evidence position — a made-up record in
`records/` would violate "no claim without a testbench" more severely than
having no record at all, and the append-only rule means it could never be
cleanly removed. The worked example below lives **in this README on
purpose**, and must stay here.

The first real testbenches landed via #4 (`devchar-delay`, `devchar-cp`,
`devchar-passives` — see each experiment's `records/` for the current
evidence). Every campaign added after them follows this same convention;
`sim/` never gains a fabricated or example record outside this file.

## Worked example (ILLUSTRATIVE — not evidence)

> **Every value below is invented for illustration.** No such record, log,
> or netlist exists in this repo; the numbers are placeholders and the spec
> anchor is a placeholder pending ratification (#1). Do **not** copy this
> block into `sim/lock-time/records/` — see "No fabricated evidence" above.

Directory layout for a closed-loop lock-time campaign (#12), showing a first
record and a later correcting re-run:

```
sim/
  lock-time/
    testbench/
      tb_lock_time.spice
      tb_lock_time.sch            # xschem source, if schematic-captured
    netlist-snapshots/
      20260730-142500-3f1c9ab.spice
      20260812-090330-b47e021.spice
    corners/
      20260730-142500-3f1c9ab/
        tt_27c_3.30v.log
        ss_-40c_2.97v.log
        ss_125c_2.97v.log
        ff_-40c_3.63v.log
        ...
        lock_transient_ss_-40c_2.97v.csv
      20260812-090330-b47e021/
        tt_27c_3.30v.log
        ss_-40c_2.97v.log
        ...
    records/
      20260730-142500-3f1c9ab.md
      20260812-090330-b47e021.md
```

`records/20260730-142500-3f1c9ab.md`:

```markdown
# Record 20260730-142500-3f1c9ab

- **Record ID**: 20260730-142500-3f1c9ab
- **Claim**: `spec/pll.md#lock-time` — worst-case cold-start lock time,
  draft target < 100 µs (placeholder value; ratified spec pending #1)
- **Netlist provenance**: schematic (`design/pll_top.sch` →
  `sim/lock-time/netlist-snapshots/20260730-142500-3f1c9ab.spice`),
  netlist SHA-256 `9f1c…a20e`
- **Environment provenance**:
  - PDK: volare `gf180mcuD`, open_pdks
    `c6d73a35f524070e85faff4a6a9eef49553ebc2b`
  - Models: `sm141064.ngspice`
  - Simulator: ngspice 46; schematic capture: xschem 3.4.7
  - Repo commit: `3f1c9ab` (clean tree)
  - Host: macOS 15 / arm64
- **Corner matrix run**: 45 PVT points (5 MOS bundles × 3 temperatures × 3
  supplies), each run at 3 divider settings → 135 runs
  - Bundles (→ `.lib` sections): `tt` → typical; `ff` → ff; `ss` → ss;
    `fs` → fs; `sf` → sf
  - Temperature: −40 °C, 27 °C, 125 °C
  - Supply: 2.97 V, 3.30 V, 3.63 V (3.3 V ±10 %)
  - **Axes not swept**: passive sections held at `res_typical`,
    `mimcap_typical`, `moscap_typical` — MOS-only sweep. Justified in
    Methodology.
  - Divider settings: N = ×4, ×16, ×64, each exercised at every one of the 45
    PVT points (worst-case step per setting)
- **Methodology / criteria / limitations**:
  - Lock criterion: cold start from `vctrl = 0`; locked when |Δf/f_target|
    ≤ 0.1 % **and** static phase error ≤ 2 % of a reference period,
    continuously for ≥ 20 reference cycles. Lock time = time from
    enable-release to the start of that window.
  - Frequency step: worst case per N — full-scale step to the band edge.
  - Transient: 400 µs, `reltol 1e-4`, max timestep 20 ps.
  - **Limitation**: passives at typical, so this record bounds lock time
    against MOS skew only; R/C skew moves loop bandwidth directly and is
    covered by the loop-dynamics campaign (#10) rather than re-swept here.
    A ratified lock-time claim must cite both.
  - Waveform retained: `lock_transient_ss_-40c_2.97v.csv`, decimated to
    2 ns/sample (worst corner only).
- **Statistical convention**: N/A — corner-matrix claim, not a distribution
  claim. Mismatch contribution to static phase error is #15
  (`mc-cp-mismatch`).
- **Result** (placeholder values):

  | Bundle | Temp | Supply | N=4 | N=16 | N=64 |
  |---|---|---|---|---|---|
  | tt | 27 °C | 3.30 V | 41 µs | 48 µs | 62 µs |
  | ss | −40 °C | 2.97 V | 63 µs | 74 µs | 91 µs |
  | ss | 125 °C | 2.97 V | 58 µs | 69 µs | 88 µs |
  | ff | −40 °C | 3.63 V | 29 µs | 34 µs | 44 µs |
  | … | … | … | … | … | … |

  - Worst point: `ss/−40c/2.97v`, N=64 → 91 µs
  - **Overall: PASS** against the draft < 100 µs target (placeholder —
    pending ratified spec, #1; margin is thin, see Methodology limitation)
- **Links**:
  - Testbench: `sim/lock-time/testbench/tb_lock_time.spice`
  - Netlist snapshot:
    `sim/lock-time/netlist-snapshots/20260730-142500-3f1c9ab.spice`
  - Raw logs: `sim/lock-time/corners/20260730-142500-3f1c9ab/`
- **Timestamp / author**: 2026-07-30T14:25:00Z, agent-builder
- **Supersedes**: (none — first record for this claim)
```

The later record `20260812-090330-b47e021.md` would be a correcting re-run —
same structure, with **Supersedes: 20260730-142500-3f1c9ab** and the reason
for the correction stated in its Methodology field (e.g. the lock criterion's
hold window was too short to exclude a late re-acquisition). The original
record stays exactly as written.

### Field variants (also illustrative)

The same schema covers the other campaign shapes. Excerpts only:

A **design-input claim** with no spec line (#4 → #10):

```markdown
- **Claim**: #4 → #10 (design input, not a spec line) — which loop-filter
  capacitor type meets the area budget with acceptable C–V linearity:
  `cap_mim_2f0fF` vs. `cap_nmos_03v3`?
- **Corner matrix run**: passive axes swept explicitly —
  `mimcap_typical/ff/ss` and `moscap_typical/ff/ss` × −40/27/125 °C;
  supply axis N/A (two-terminal C–V sweep over 0…3.63 V control range);
  MOS process bundles N/A (no active devices in the DUT).
- **Result**: comparison table (density fF/µm², ΔC/C over control range,
  leakage @ 125 °C) → conclusion: MIM at 2.0 fF/µm² fits the area budget
  with < 1 % ΔC/C; MOS cap is denser but non-linear over the control range.
```

A **recorded methodology gap** instead of a number (#13):

```markdown
- **Claim**: `spec/pll.md#period-jitter` — random (noise-driven) period
  jitter, draft target < 1 % RMS (placeholder; pending #1)
- **Methodology / criteria / limitations**: ngspice transient-noise analysis
  on a full closed-loop PLL at these transient lengths does **not** produce
  a convergent RMS estimate on this flow — [specific evidence and settings
  tried]. **No random-jitter number is reported by this record.**
  Deterministic jitter (control ripple, divider pattern) is reported below
  and is credible. Feeding back to #1/#7: the ratified jitter claim must be
  stated as deterministic-only in simulation, with random jitter deferred to
  silicon measurement (`measurements/`).
- **Result**: deterministic period jitter per corner (table); random jitter:
  **not substantiated — see Methodology**. Overall: **spec claim not
  verifiable by this method**, not "PASS".
```

A **distribution claim** with the statistical convention (#15):

```markdown
- **Corner matrix run**: nominal corner (`tt/27c/3.30v`) only — mismatch
  distribution evaluated at nominal PVT; corner sensitivity of the mean is
  covered by the corner-matrix record for the same block.
- **Statistical convention**: N = 500 Monte Carlo samples, mismatch-only
  (device mismatch model enabled, process variation disabled), distribution
  reported at ±3σ; seed recorded in the log header.
- **Result**: ±3σ static phase error and worst-case reference spur level
  (placeholder values) — **Overall: PASS** (placeholder, pending #1)
```

## For the harness (#2)

The harness bootstrapped in #2 is the intended producer of these records: it
owns the environment (`.lib` sections, `.temp`, supply) and must emit, per
run, the frozen netlist snapshot, the per-corner logs, and the Markdown
summary record with every mandatory field populated. Machine-readable
side-artifacts (JSON/CSV) are welcome **in addition**; they do not replace
the Markdown record. Conformance is verified when #2 lands, not here.

**#2 has landed** as `sim/harness/` (`pdk.py` / `corners.py` / `testbench.py`
/ `runner.py` / `report.py` / `cli.py`), `sim/run_corners.py`, `sim/env.sh`
and `sim/selftest.sh` — see `sim/harness/README.md` for how to run it and how
to write a testbench manifest. `sim/harness-selftest/` is the harness's own
acceptance testbench (real devices, real corners, no design claim); it is not
one of the block campaigns in the table above. The interim `sim/lib/simenv.sh`
shim and the `sim/devchar-*` / `sim/divider-ratio` / `sim/lock-detector` /
`sim/cp-compliance` / `sim/pfd-deadzone` / `sim/vco-tuning-range` campaigns
built on it remain the real, already-recorded evidence for their claims;
migrating them onto `sim/harness` is tracked separately (see the issue that
follows #2) rather than done as part of landing the harness itself, so that
already-citable PVT evidence is not touched in the same change that
introduces the tool that will eventually reproduce it.
