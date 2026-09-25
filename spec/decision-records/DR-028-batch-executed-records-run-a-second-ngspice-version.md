# DR-028: The batch backend's job image runs ngspice-42 against this repository's ngspice-46 pin; the divergence is ratified and disclosed, and batch-executed numbers are quarantined from cross-version comparison until an overlap measurement bounds it

- **Status**: proposed, drafting for operator ratification via PR review — the
  same route DR-007, DR-009 … DR-020 record (a builder drafts the record on the
  evidence; the operator's PR approval is the ratifying act). Status stays
  `proposed` until that approval and merge.
- **Date**: 2026-09-25
- **Decided by**: Builder agent, issue #536
- **Numbering note**: `DR-027` is claimed by open PR #535 (unmerged at the time
  of writing), so this record takes `028` to avoid a duplicate number, per the
  collision rule in `TEMPLATE.md`. If PR #535 is abandoned, `027` stays an
  unused gap — `DR-NNN` is a stable identifier, not a dense sequence, and
  renumbering a merged record would break every reference to it.

## Context

`sim/README.md`'s [ngspice binary pin (#259)](../../sim/README.md) section
pins the simulator for every `sim/lib/simenv.sh`-based campaign to
`$HOME/.local/bin/ngspice` — **ngspice-46** — and treats the version as part
of a run's identity: `sim/README.md`'s environment-provenance contract
requires every record to name its simulator version, because model sections,
integration behaviour and measurement handling are all properties of the
binary, not only of the deck. The pin exists for a measured reason (#259,
#153): a host missing it fell through `PATH` to Homebrew's ngspice-47, which
hits a reproducible parse failure on this PDK's nested nonlinear moscap family
(`cap_*mos_03v3`/`06v0`) and **hung instead of exiting**, stalling a job pool.

The batch execution backend (`sim/harness/batch.py`, `sim/run_corners.py
--backend batch`) runs one job per composed deck on an external, operator-owned
execution layer. This repository writes a shell-command job contract and knows
nothing about instances or images; the layer runs jobs and knows nothing about
ngspice. **The job image's simulator is therefore outside this repository's
pin, and outside anything a PR here can change.**

### The fact, re-derived here rather than restated

A decision about committed evidence should rest on something a stranger can
re-run. The batch-executed corner logs print the simulator's own sign-off line,
and it does not say 46:

```
$ gh api repos/2AMLogic/gf180-pll/contents/sim/reference-phase-transfer/corners/\
20260925-080736-b722f33/ctl_typical_27c_3.30v_vs1p795.log?ref=262c1e59 \
    --jq .content | base64 -d | tail -1
ngspice-42 done
```

**Provenance caveat, stated up front**: that log — and the three
`sim/reference-phase-transfer` records it belongs to — exists **only on PR
#535's branch** (head `262c1e595d9959b9f349964fddbefaa39a0eaff5`, verified
2026-09-25), which is unmerged. On `origin/main` at `e341b585` the tree
contains **zero batch-executed records**. So the blast radius of this record
today is not a set of committed numbers; it is the *next* campaign to use the
backend — #499, #503 and #533 all name it as the route to their owed 45-point
grids. That is why this is worth deciding before the backend is used more
widely rather than after.

### What is at stake, and what is not

It is **not** a claim that the ngspice-42 numbers are wrong. Those grids
converged and passed their own lock guards, and the pin's known defect (#153)
is an ngspice-**47** parse failure — ngspice-42 is *older* than the pin, parsed
this PDK's moscap family without complaint, and shows no sign of that failure
mode. Nothing here impeaches the measurement on its own terms.

What it costs is **comparability**. Four ngspice releases separate 42 from 46,
spanning changes this repository has never characterised for these decks, and
**no measurement exists in either direction** — nobody has run the same
operating point on both. On a supersession edge ("did the number move because
the design changed, or because the simulator did?") that unknown is not
academic, it is the whole question.

### The reproducibility floor an overlap measurement has to be read against

This repository already has one worked overlap measurement, across *hosts*
rather than versions, and it is the shape the missing one should take.
`sim/period-jitter`'s record `20260906-063728-f3c9c23` deliberately re-ran two
27 °C/3.30 V points that record `20260906-015602-f9bef9d` had already taken —
"those were taken with ngspice-46 on Linux/x86-64 and are re-taken here with
ngspice-46 on macOS/arm64, so they double as a cross-host reproducibility
check". Re-deriving the agreement from the two committed records' own
period-jitter columns (same simulator version on both sides):

| Point | Linux/x86-64 (`…f9bef9d`) | macOS/arm64 (`…f3c9c23`) | Relative difference |
|---|---|---|---|
| `ff_27c_3.30v_vs1p931` | 0.207204 % | 0.214900 % | **+3.71 %** |
| `ss_27c_3.30v_vs1p633` | 0.133303 % | 0.145709 % | **+9.31 %** |

Two things follow, and both matter for what this record decides. First, an
overlap measurement is cheap, already precedented here, and the right
instrument. Second — **the same-version, cross-host floor on this quantity is
already several percent**, so a cross-*version* overlap only bounds anything if
it is read against that floor rather than against zero. A future measurement
that finds, say, 4 % has not shown the versions agree; it has shown the
divergence is not resolvable above this design's own host-to-host spread.

## Decision

**1. The divergence is recorded, with both versions named.** The batch job
image runs **ngspice-42**; this repository pins **ngspice-46**. A record whose
points executed off-host was taken on a simulator this repository does not pin,
and `sim/README.md`'s pin section now says so rather than leaving a reader to
infer alignment from the pin's existence.

**2. Disclosure on the record's own face is mandatory, not optional.**
`sim/README.md`'s environment-provenance contract already requires a
batch-executed record to name the execution backend and the hosts that ran the
points; it now additionally requires the **executing simulator version**
whenever that differs from the `Simulator:` bullet — which, under an off-host
backend, reports the version resolved on the *submitting* host, a host that ran
no deck at all. Automatic reporting of this arrives with #509 (PR #535's
`Executing simulator:` line); until that merges the record's author writes it
by hand. A batch-executed record that does not disclose its executing simulator
version is incomplete evidence, not merely untidy.

**3. Batch-executed numbers are quarantined from cross-version comparison
until a measurement bounds the divergence.** They remain evidence on their own
terms — self-consistent within their own grid, guarded identically, citable as
what they are. They may **not**:

  - **(a)** supersede a locally-executed ngspice-46 record;
  - **(b)** be composed point-for-point with ngspice-46 numbers into one
    corner-consistent total (a worst-of across the two sets is a worst-of
    across two simulators);
  - **(c)** be quoted as completing a PVT grid whose other points were taken on
    the pin — a mixed-version grid must state the split, per Decision 2.

A batch-executed record that stands alone, cited as a batch-executed record, is
unaffected by all three.

**4. The bound is owed, named, and deliberately not guessed at.** What
discharges Decision 3 is a **cross-version overlap measurement**: at least one
shared operating point measured on both the job image and the pinned local
binary, both numbers reported side by side in one record, in the shape
`sim/period-jitter`'s cross-host overlap already demonstrates — and read
against the several-percent same-version floor quantified in §Context. **This
record takes no such measurement and quotes no number for the divergence's
size.** It is tracked at **#549**. When it lands, a successor record may relax
Decision 3 to the measured bound; if the image is realigned instead, a
successor record supersedes this one outright.

**5. Alignment (rebaking the image at ngspice-46) remains the preferred
resolution, and ratifying the divergence does not close it.** The image is
built by operator-owned provisioning outside this repository; nothing in a PR
here can change it, which is the only reason this record exists instead of that
fix. It is #536's option 1 and it stays open.

**6. No spec row moves, and no `sim/` record changes.** `spec/pll.md` is
byte-identical after this record. No evidence record is added, superseded or
rewritten, and no number anywhere in `sim/` changes. This is a decision about
what committed numbers may be *compared with*, not about any number's value.

**7. No `2AMLogic/klayout-tools` issue is owed for this.** CLAUDE.md's friction
protocol covers gaps in `klt`; this is a SPICE execution-environment gap with
no layout component. Stated so a reader does not read the protocol as skipped.

## Alternatives considered

- **Rebake the job image at ngspice-46 (#536 option 1) instead of ratifying
  anything.** Not rejected — it is the better outcome and Decision 5 keeps it
  open. It is not *chosen here* because no change in this repository can
  execute it: the image belongs to operator-owned provisioning outside this
  tree. A record that says "the right fix is elsewhere" and leaves the interim
  state undocumented is the failure this record exists to avoid.
- **Make the backend refuse to run when the image's version does not match the
  pin (#536 option 3).** Rejected, and named so the rejection is visible rather
  than silent. It is the cheapest to implement and the worst outcome: off-host
  execution is currently the only route this repository has to its owed
  closed-loop grids (#499, #503, #533), so fail-fast converts a disclosed,
  bounded comparability problem into no evidence at all. Refusing to measure is
  not a way of measuring carefully.
- **Assert equivalence on plausibility — "four releases would not move a period
  measurement".** Rejected. It is a plausible expectation and it is not a
  measurement; ratifying it would put an invented bound into the spec, which is
  exactly what "no claim without a testbench" forbids. The cross-host table in
  §Context shows the quantity moves by 3.7–9.3 % across *hosts* at a fixed
  version, which is reason to expect version effects to be measurable, not
  reason to assume they are zero.
- **Take the overlap measurement inside this record by building ngspice-42
  locally.** Rejected as a proxy that answers a different question. The quantity
  at issue is the *job image's binary* — its build flags, linear solver, math
  library, architecture and OS — not the version string alone. A macOS/arm64
  build of ngspice-42 would change the build and the host at the same time as
  the version, so neither agreement nor disagreement could be attributed to the
  version, and reporting it as the batch-vs-local bound would overstate what was
  measured. The measurement that answers the question needs a fleet submission,
  which spends from a shared budget behind `--batch-apply` and operator-owned
  credentials — hence #549 rather than a number here.
- **Hold this record until the measurement exists.** Rejected on DR-020's
  reasoning. The divergence is live now and the backend is named as the route
  for three owed campaigns; deferring leaves the next batch-executed record
  landing with no written rule about what it may be compared with, which is the
  defect being repaired. The restriction in Decision 3 is also the one part that
  needs no measurement to justify — it is a *limit* on what may be claimed, and
  limits do not require evidence, relaxations do.
- **Quarantine harder — forbid batch execution for evidence entirely until the
  image is aligned.** Rejected: that is option 3 in a different wrapper, with
  the same consequence for #499/#503/#533 and without even the disclosed record
  to show for it.
- **Record the divergence in `sim/README.md` alone, with no decision record.**
  Rejected. Decision 3 restricts what committed evidence may be claimed to show,
  which is a normative statement about the verification contract — CLAUDE.md
  routes those through `spec/` with a decision record, and a rule that lives
  only in a README paragraph has no supersession trail when #549 relaxes it.

## Consequences

- **`sim/README.md` changes in two places and no number moves.** The pin
  section now states which of "aligned" or "ratified divergence" holds for the
  batch backend (divergence, this record, bound owed at #549), and the
  environment-provenance contract's off-host bullet now requires the executing
  simulator version alongside the executing hosts.
- **The next batch-executed campaign inherits Decision 3 before it runs.**
  #499, #503 and #533 each plan a 45-point grid on this backend. Under this
  record those grids are citable as standalone batch-executed evidence and are
  **not** supersession candidates for the pinned-local records beside them
  until #549 lands or the image is realigned. That is a real constraint on how
  their results may be written up, and it is better known before the spend than
  after.
- **`sim/reference-phase-transfer`'s three records (PR #535's branch) are
  covered the moment they merge**, with no edit to them: they stand as
  batch-executed evidence, disclosing their executing simulator, superseding
  nothing taken on the pin. #536's acceptance criterion 3 — re-take that grid on
  an aligned image and supersede `20260925-080736-b722f33` — is a *consequence
  of option 1*, not of this record, and stays owed to whoever aligns the image.
- **The bad consequence, stated plainly.** This record quotes no bound. It
  converts an undisclosed unknown into a disclosed, owned unknown with a named
  exit condition, and that is all it does. Until #549 or a rebaked image lands,
  off-host execution buys throughput at the price of evidence that cannot be
  composed with the rest of `sim/` — and for a repository whose product is
  verification, a grid that cannot be composed with its neighbours is worth
  materially less than its point count suggests. Anyone reading a
  batch-executed record will find a number they may cite and may not merge into
  the surrounding evidence, and should.
- **Nothing in `design/`, `layout/`, `signoff/` or `spec/pll.md` changes**, no
  schematic, no netlist, no GDS, and the append-only trees are untouched.
