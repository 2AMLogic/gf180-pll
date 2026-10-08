# DR-039: The batch job image now signs off ngspice-46 and converges the six `wedge` −40 °C points DR-035 found it failing; DR-028's version fact and Decision 5 are discharged, and its Decision 3 quarantine is relaxed only for the one deck and quantity the overlap covers

- **Status**: proposed, drafting for operator ratification via PR review — the
  same route DR-007, DR-009 … DR-038 record (a builder drafts the record on the
  evidence; the operator's PR approval is the ratifying act). Status stays
  `proposed` until that approval and merge.
- **Date**: 2026-10-08
- **Decided by**: Builder agent, issue #680
- **Revises**: DR-028 (Decisions 1, 3 and 5, in part), DR-035 (Decision 4, whose
  prerequisite is now met for the probe). Neither is rewritten; DR-028's status
  line carries a pointer to this record.

## Context

DR-028 recorded that the batch backend's job image runs **ngspice-42** against
this repository's **ngspice-46** pin (`sim/README.md`, "ngspice binary pin
(#259)"), ratified the divergence, quarantined batch-executed numbers from
cross-version comparison (Decision 3), and kept realigning the image as the
preferred resolution (Decision 5, "option 1"). DR-035 then measured that the
image's ngspice-42 aborts with `Timestep too small … trouble with node
"vctrl#branch"` on the `wedge` variant of `sim/reference-input-contract` at
every −40 °C point it reached, promoted option 1 to *required for #499*, and
gave it an open owner, #680.

Operator-owned provisioning (2AMLogic/2am#1885, merged 2026-10-02) has since
rebuilt the image with ngspice-46. This record is the repository's own
re-verification of that claim, taken the way DR-028 says it should be taken —
from a batch-executed corner log's own sign-off line — and not restated from
the provisioning change.

### What was run

The six-point probe DR-035 and #680 name, on the **batch** backend this time:

```bash
python3 sim/run_corners.py reference-input-contract \
    --corners typical ff --temps -40 --supply 3.3 --supply-tol 0.1 \
    --axis w=wedge --axis p=p0 --no-write -j 2 \
    --backend batch --batch-apply
```

PVT: corners `typical` and `ff`; −40 °C; supply 2.97 / 3.30 / 3.63 V
(3.30 V ± 10 %); `wedge` waveform; `p0`. Run on 2026-10-08, harness record id
(not minted, `--no-write`) `20261008-093924-eac582a`; six fleet jobs named
`gf180-pll-sim-<point>-<suffix>`, e.g.
`gf180-pll-sim-typical_-40c_3.30v_wedge_p0-abaedf93`.

### Observed

**Version.** All six jobs' own logs end `ngspice-46 done`, and the harness's
executing-simulator summary reads `simulator(s) ngspice-46 (6)`. Each job's
`ngspice.env` shows the banner `ngspice-46 : Circuit level simulation program,
Compiled with KLU Direct Linear Solver, Creation Date Thu Oct 1 23:51:59 UTC
2026`, the PDK stamp `open_pdks c6d73a35f524070e85faff4a6a9eef49553ebc2b`
(the revision this repository's decks are stamped with), and the image
manifest (`built_at` 2026-10-02T15:02:12Z, `tools.ngspice` `ngspice-46`). The
`ngspice:` header line in the run's console output (`ngspice-42`) is the
*submitting* host's simulator, not the executor's; the submitting worker does
not carry the pin. That header is not evidence either way.

**Convergence.** Six of six points converged (exit status 0 on the one
`ngspice.rc` inspected; all six harness lines `ok`), where DR-035 recorded
0 of 6 on the ngspice-42 image.

**Overlap with the pin.** `d_ref` on the image, against the pin's values
recorded in DR-035 §Context for the same six points:

| `-40 °C` `wedge` point | `d_ref`, image (ngspice-46) | `d_ref`, pin (DR-035) |
|---|---|---|
| `typical_-40c_2.97v_wedge_p0` | 2.859580e-10 | 2.859580e-10 |
| `typical_-40c_3.30v_wedge_p0` | 2.563880e-10 | 2.563880e-10 |
| `typical_-40c_3.63v_wedge_p0` | 2.419830e-10 | 2.419830e-10 |
| `ff_-40c_2.97v_wedge_p0`      | 2.248270e-10 | 2.248270e-10 |
| `ff_-40c_3.30v_wedge_p0`      | 2.088670e-10 | 2.088670e-10 |
| `ff_-40c_3.63v_wedge_p0`      | 2.030940e-10 | 2.030940e-10 |

Identical to the printed seven digits at all six points, i.e. a same-version
cross-host difference below the resolution of the report, against the
several-percent floor DR-028 §Context quantified on `sim/period-jitter`. Only
`d_ref` was recorded on the pin side in DR-035, so only `d_ref` is compared;
the image-side values of the other quantities are in the run's console output
and are not reproduced as agreement here because there is nothing recorded to
compare them against.

**The probe is not a record.** `--no-write`: it mints no evidence, covers one
corner family of forty-five and one waveform variant of six, and no number in it
reaches `spec/pll.md` or `docs/chipalooza/`. `tb.json`'s `min_measured_points:
288` guard correctly reports `got 6` and the run's exit status is non-zero for
that reason alone.

### What this does not show

A same-day diagnostic, `sim/BATCH-IMAGE-DIAGNOSIS-2026-10-08.md` (#533, #503),
found that on **other decks** (`reference-spur-band-top`, the period-jitter
pilot) the image's ngspice-46 takes a different DC operating-point path from
the pinned local ngspice-46 (dynamic and true gmin stepping where the local
binary converges by direct Newton) and lands in the other state of a bistable
PFD latch, with the cause unresolved. The same gmin-stepping prologue appears in
the inspected `wedge` job's log here (lines 1–4 of `ngspice.log`), yet `d_ref` matches
the pin to seven digits on these six points. So a matching version string is
necessary and, as that note shows, not sufficient for batch and pinned-local
results to be interchangeable; this record cannot generalise from the one deck
whose overlap it measured.

## Decision

**1. DR-028's version fact is superseded.** The batch job image signs off
**ngspice-46**, the same version as the pin, verified from batch-executed corner
logs on 2026-10-08. `sim/README.md`'s pin section is updated to say so, and no
longer says the image signs off `ngspice-42`.

**2. DR-028 Decision 5 (alignment) is discharged for the version.** Option 1
was taken by operator-owned provisioning. #680 acceptance criteria 1 and 2 are
met; the remaining criterion (the 288-point grid) is #499's own run.

**3. DR-028 Decision 3 (the quarantine) is relaxed only as far as the evidence
reaches.** For `sim/reference-input-contract`, whose `d_ref` agrees with the pin
at all six overlap points above, a batch-executed record of that campaign is
**not** quarantined from pinned-local `d_ref` numbers taken on ngspice-46.
Everywhere else Decision 3 stands as written, with its reason changed from
"different version" to "unbounded divergence": no other campaign has an overlap
point, and the 2026-10-08 diagnostic shows a version match does not guarantee
one. A campaign that wants the same relaxation supplies its own overlap
points, read against DR-028's cross-host floor. The relaxation does **not**
cover the charge quantities (`qnet`, `qnet2`) of `reference-input-contract`
either: the only overlap recorded for them is DR-035's 17 % ngspice-42 versus
ngspice-46 difference, and no ngspice-46 versus ngspice-46 charge overlap has
been taken.

**4. DR-035's other decisions stand unchanged.** `spec/pll.md`'s Reference input
lines stay **budget**: no record exists. The deck is not retuned. The
partial-run-not-committed rule stays. Wording in `spec/pll.md`,
`sim/CHARACTERIZATION.md` and `docs/chipalooza/challenge-5-proposal.md` that
names the image's ngspice-42 as the *current* blocker gains a pointer to this
record; the requirement text, the budget status and every number are untouched.

**5. #499's grid is the next step and is not run here.** Its first submission
must go through `--backend batch --batch-apply` as DR-035 and the host rules
require. If any of its `wedge` points fail on the fleet, that is new evidence
and a new record, not a reason to reopen this one.

## Alternatives considered

- **Supersede DR-028 outright and declare the quarantine moot.** Rejected: the
  same-day diagnostic shows image-versus-pin divergence on decks other than this
  one at an identical version string. Declaring comparability from the version
  alone would assert the thing DR-028 refused to assume.
- **Keep DR-028 Decision 3 verbatim.** Rejected as unsupported in the other
  direction: six overlap points at seven-digit agreement on the quantity this
  campaign grades is a measurement, and refusing to credit it would leave
  `reference-input-contract` quarantined for a version difference that no longer
  exists.
- **Run the full 288-point grid now to settle it.** Out of scope: a separate,
  long fleet run owned by #499, with its own budget and its own record.
- **Retune the deck.** Moot (the points converge) and still wrong for the
  reasons DR-035 Decision 3 gives.

## Consequences

- #499 is unblocked on the version prerequisite; its grid and record are still
  owed, and every Reference input line remains **budget** until they exist.
- `sim/README.md`'s pin section no longer describes the image as ngspice-42. It
  keeps the quarantine for every other campaign and points to the diagnostic.
- A reader of `reference-input-contract`'s eventual batch record may compare its
  `d_ref` with ngspice-46 results from the pin; may not compare its charge
  quantities or any other campaign's batch numbers without overlap points.
- Bad consequence, stated plainly: the relaxation rests on six points of one
  quantity on one waveform variant, and the six pin values are the ones DR-035
  recorded, not a fresh pin run (the submitting worker does not carry the pin).
- No schematic, netlist, layout, `spec/pll.md` requirement, or `sim/` evidence
  record changes.
