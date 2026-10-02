# DR-035: The Reference input campaign's owed grid is blocked by the batch job image's simulator, not by compute; the cross-version divergence DR-028 owed is measured, and the deck is deliberately not retuned to accommodate ngspice-42

- **Status**: proposed, drafting for operator ratification via PR review — the
  same route DR-007, DR-009 … DR-034 record (a builder drafts the record on the
  evidence; the operator's PR approval is the ratifying act). Status stays
  `proposed` until that approval and merge.
- **Date**: 2026-10-02
- **Decided by**: Builder agent, issue #499

## Context

DR-019 re-pointed `spec/pll.md`'s [Reference input](../pll.md#reference-input)
row off closed issue #12 and onto `sim/reference-input-contract` (#499), a
campaign whose manifest, deck and reduction are committed and self-checking and
whose 288 declared points were, at that time, entirely unmeasured. Every
document that cites it — `spec/pll.md`'s
[Verification owed](../pll.md#verification-owed) table, `sim/CHARACTERIZATION.md`
and `docs/chipalooza/challenge-5-proposal.md` §5 — says what remains there in
the same words: **"what is owed is compute, not mechanism or design."**

That sentence is now known to be false, and this record is what replaces it.

### What was attempted

The grid was submitted to the batch execution backend
(`sim/run_corners.py --backend batch --batch-apply`), which is the route this
repository's operating rules require for a multi-corner grid and the route
DR-028 §Consequences names for this campaign. The submission reached the fleet
and ran: 118 of 288 points executed before the run ended. Two separate things
went wrong, and they are different in kind.

### Finding 1 — the fleet's concurrency ceiling aborted the grid (repaired here)

```
error: BackendError: batch backend: launching
  gf180-pll-sim-ff_125c_2.97v_wd70_p0-b7042709 failed (exit 1):
  error: 9 instance(s) already running + 1 requested exceeds
  BATCH_MAX_CONCURRENT_INSTANCES=8
```

The execution layer caps concurrent instances **fleet-wide**, across every
campaign submitting to it. `sim/harness/batch.py`'s `_launch` raised that
refusal as a `BackendError`, which propagates out of the point and ends the
whole run — 170 points were never submitted. Two things make that the wrong
behaviour rather than merely unlucky: the refusal is *transient by
construction* (the instances it counts are finishing), and it is **not
avoidable by choosing a smaller `-j`**, because the instances it counts are not
this run's. It is also at odds with the rule the harness states for itself in
`runner.py`'s `_write_log` — a per-point failure "must degrade that one point
rather than raising out of `run_grid` and discarding every other point the grid
already completed."

This is a defect in this repository and it is fixed in the same change as this
record: a ceiling-named refusal is waited out and the same job id re-offered,
bounded at `LAUNCH_CEILING_ATTEMPTS`; a refusal that is *not* the ceiling (the
subnet-resolution failure of #509, say) still fails fast. It is **not** the
reason the campaign is undischarged, and it is recorded here only so a reader
does not mistake Finding 2 for it.

### Finding 2 — the job image's ngspice-42 cannot run this campaign

Of the 118 points that executed, **12 failed to converge, and all 12 are the
same waveform variant**: `wedge`, the full-rail 6.25 ns-ramp pulse that puts
the 10–90 % edge rate at exactly 5.00 ns. That variant **is** the binding point
of the contract's edge-rate budget. Every failure is the same solver abort, at
a breakpoint of the slow ramp:

```
doAnalyses: TRAN:  Timestep too small; time = 7.6975e-08,
  timestep = 2.5e-23: trouble with node "vctrl#branch"
```

(`7.6975e-08` and `9.6975e-08` are the falling edge of the second reference
cycle and the rising edge of the third; no other variant failed at any point.)

| `wedge` on the job image (ngspice-42) | attempted | converged | failed |
|---|---|---|---|
| all corners reached before the abort | 20 | 8 | **12** |

The failures are not scattered: every one of the nine `-40 °C` points reached
failed, as did `ff` at 27 °C at all three supplies. The eight that converged
are `typical` at 27 °C and 125 °C, plus two 2.97 V outliers.

**The same points converge on the simulator this repository pins.** Re-run
locally on `$HOME/.local/bin/ngspice` (**ngspice-46**, the #259 pin, verified
by `sim/run_corners.py --check-env`):

```bash
python3 sim/run_corners.py reference-input-contract \
    --corners typical ff --temps -40 --supply 3.3 --supply-tol 0.1 \
    --axis w=wedge --axis p=p0 --no-write -j 2
```

| `-40 °C` `wedge` point | ngspice-42 (job image) | ngspice-46 (pin) | `d_ref` on the pin |
|---|---|---|---|
| `typical_-40c_2.97v_wedge_p0` | **no convergence** | ok | 2.859580e-10 |
| `typical_-40c_3.30v_wedge_p0` | **no convergence** | ok | 2.563880e-10 |
| `typical_-40c_3.63v_wedge_p0` | **no convergence** | ok | 2.419830e-10 |
| `ff_-40c_2.97v_wedge_p0` | **no convergence** | ok | 2.248270e-10 |
| `ff_-40c_3.30v_wedge_p0` | **no convergence** | ok | 2.088670e-10 |
| `ff_-40c_3.63v_wedge_p0` | **no convergence** | ok | 2.030940e-10 |

**0 of 6 on the image; 6 of 6 on the pin.** This is a 6-point debug probe, not
a record, and it mints none — it is one corner family of forty-five and no
number in it reaches `spec/pll.md` or `docs/chipalooza/`.

### The cross-version overlap DR-028 Decision 4 owed, measured

DR-028 ratified the image/pin divergence, quarantined batch-executed numbers
from cross-version comparison, and said in as many words that it **"takes no
such measurement and quotes no number for the divergence's size"**, filing the
bound at **#549**. What discharges that is "at least one shared operating point
measured on both the job image and the pinned local binary, both numbers
reported side by side in one record."

That measurement is cheap and is taken here. `typical_-40c_3.30v_wideal_p0` —
the campaign's own *anchor* waveform, the ideal full-rail 200 ps pulse every
other deck in this repository drives — run on both, same deck, same point:

```bash
# job image (ngspice-42)
python3 sim/run_corners.py reference-input-contract \
    --corners typical --temps -40 --supply 3.3 --supply-tol 0 \
    --axis w=wideal,wedge --axis p=p0 --no-write \
    --backend batch --batch-apply -j 2 --timeout 900
# pin (ngspice-46) -- the same command without the two --backend/--batch flags
```

| quantity | ngspice-46 (pin) | ngspice-42 (job image) | relative difference |
|---|---|---|---|
| `d_ref` | 2.779070e-10 | 2.777844e-10 | **−0.044 %** |
| `d_fb` | 2.553670e-10 | 2.552115e-10 | **−0.061 %** |
| `width_up` | 1.406270e-09 | 1.406679e-09 | **+0.029 %** |
| `width_dn` | 1.427160e-09 | 1.427605e-09 | **+0.031 %** |
| `qnet2` | −3.130610e-15 | −2.596250e-15 | **−17.07 %** |
| `qnet` | −1.565300e-15 | −1.298130e-15 | **−17.07 %** |
| `slew_ref` | 1.600000e-10 | 1.600000e-10 | 0 |
| `thigh_ref` | 2.000000e-08 | 2.000000e-08 | 0 |

Read against the **several-percent same-version, cross-host floor** DR-028
§Context quantified from `sim/period-jitter`'s own two records (3.71 % and
9.31 % on a period-jitter figure), this says something specific and
two-sided:

- The **timing** quantities — the ones this campaign grades — agree to better
  than 0.1 %, i.e. **well inside** that floor. On `d_ref` the two versions are
  not resolvably different.
- The **charge** integral disagrees by **17 %**, i.e. **well outside** it. A
  `qnet`-based claim composed across the two versions would be comparing
  simulators, exactly as DR-028 Decision 3(b) forbids.

So the divergence is not one number. It is small on delays and large on
integrated current, which is why DR-028's blanket quarantine was the right
call on no evidence, and why relaxing it needs per-quantity care rather than a
single factor.

## Decision

**1. `spec/pll.md`'s Reference input row keeps every requirement it has, and
its three unmeasured lines stay `budget`.** V_IL ≤ 0.2·VDD, V_IH ≥ 0.8·VDD,
≤ 5 ns 10–90 % edges and 30–70 % duty all stand exactly as ratified. Nothing in
this record relaxes, reinterprets or narrows the contract. Nothing in it
measures the contract either.

**2. What the row says is *owed* changes, because the old statement is false.**
Every place that says the campaign needs "compute, not mechanism or design"
is corrected to name the actual blocker: **the batch job image runs ngspice-42,
which does not converge on the `wedge` variant across much of the mandated
grid, and `wedge` is the edge-rate budget's binding point.** The grid is
therefore **not obtainable on the current image at any budget**, and this is a
stronger statement than "unmeasured": a reader who sees "compute is owed" will
conclude correctly that money discharges it, and that conclusion is wrong.

**3. The deck is deliberately not retuned to make ngspice-42 converge.**
Rejected explicitly rather than silently (see §Alternatives). The campaign's
methodology claims its charge numbers are *directly comparable* with
`sim/pfd-deadzone`'s because every solver option is that campaign's, unchanged;
the knobs that would move a `Timestep too small` abort (`trtol`, `method`, the
tolerances) are integration controls, so buying convergence with them would
move the numbers and forfeit that comparability — to satisfy a simulator this
repository does not pin.

**4. The owner of the remaining work is named, and it is not compute.**
Discharging #499's AC 1 requires the job image realigned to the ngspice-46 pin
— DR-028 Decision 5's **option 1**, which that record left open as "the
preferred resolution". This record upgrades it from preferred to **required for
#499**: until it lands, the campaign has no route to a complete grid. The image
is built by operator-owned provisioning outside this repository, so this is
recorded, not fixed, here.

**And it is given an open owner, #680, rather than cited to a closed one.**
#536 is where option 1 was raised, and #536 is **closed** — it took option 2
(ratify the divergence) because no PR here can rebake an operator-owned image.
Citing "#536 option 1" as the prerequisite would therefore have pointed a live
obligation at a closed issue, which is *precisely* the defect #499 was filed
about and DR-019 repaired one row up. The requirement is unchanged; what this
adds is an owner that is actually open. #536 is still named everywhere as the
origin of the option, marked closed.

**5. DR-028 Decision 4's owed overlap bound is measured, and DR-028 Decision 3
is *not* relaxed by it.** The table in §Context is offered as the measurement
#549 asks for, on this campaign's own deck. It is **one point and one deck**,
so it bounds the divergence for `reference-input-contract`'s quantities and for
nothing else; `sim/period-jitter`'s or `sim/reference-phase-transfer`'s
quantities are not covered by it and the quarantine continues to apply to them
unchanged. Decision 3's three prohibitions stay in force as written. A
successor record may relax them per-quantity once there are overlap points on
the decks that need it; this record does not pre-authorise that.

**6. The 118-point partial run is not committed.** It mints no record, and the
two partial records its two aborted attempts produced were deleted rather than
committed. A grid that lost the binding point of the very budget it exists to
measure is not partial evidence for that budget; it is evidence about the
simulator, which is what §Context uses it for. `sim/reference-input-contract`
therefore still has **zero committed records**, and every document continues to
disclose it as declared-and-unmeasured.

**7. The source-quality exclusion is unchanged.** DR-019 Decision 3 stands in
full — the exclusion, its boundary, its unowned status and `dtdv_worst` as the
input-side coefficient an integrator is owed. `dtdv_worst` is derived from the
measured edges of the slow-edge variants, so it is blocked behind Decision 4
along with everything else this campaign owes. Nothing here moves it.

## Alternatives considered

- **Run the 288-point grid locally on the pinned ngspice-46.** It would work:
  the pin converges on every point the image failed, and the resulting record
  would be *more* valuable than a batch one, since it would be comparable with
  every other record in `sim/` instead of quarantined under DR-028 Decision 3.
  Rejected because the dispatch host's operating rules forbid it in terms that
  fit this situation exactly — "if a batch submit fails, report the error in
  your PR/issue, do not fall back to running the whole grid locally" — on a
  shared 8-core box running up to twelve concurrent sweeps. The 288 points are
  roughly 80 minutes of saturated CPU that other sweeps would pay for. This is
  the one alternative that would have discharged AC 1 today, and it is declined
  on an operating rule rather than on an engineering judgement; that is stated
  plainly so the operator can overrule it cheaply if the rule's intent does not
  reach this case.
- **Accept 276 of 288 points and record the grid with the 12 `wedge` corners
  missing.** Rejected. The manifest's own `min_measured_points: 288` would
  refuse it, and that guard is right: the missing points are not a random
  thinning but *precisely* the variant that tests the edge-rate budget, at
  precisely the cold corners where a slow edge is hardest. A record that
  dropped them would discharge the levels and duty lines while quietly leaving
  the edge-rate line in exactly the budget state #499 was filed about.
- **Retune the deck's solver options until ngspice-42 converges.** Rejected,
  per Decision 3. Two reasons, either sufficient: it would move the numbers and
  break the stated bit-comparability with `sim/pfd-deadzone`, and it would
  shape a committed deck around a simulator this repository does not pin —
  inverting the pin's purpose, which is that the binary is part of a
  measurement's identity (#259, DR-028 Decision 1).
- **Build ngspice-42 locally and debug the convergence there.** Rejected on
  DR-028's own reasoning, restated: a local build of 42 changes the build, the
  libraries and the host at the same time as the version, so it answers a
  different question than "what does the job image do". It would also be work
  spent making an unpinned simulator run a deck nobody intends to measure on.
- **File this as a `reference-input-contract` record with status `FAIL` so the
  numbers are committed somewhere.** Rejected. `sim/` records are append-only
  evidence about *the design*; a record whose verdict is "the simulator did not
  converge" would sit in the campaign's chain implying the campaign failed, and
  a future reader comparing records would have to know to discount it. The
  §Context tables plus the two exact re-run commands put the same facts where
  they belong — in the decision that depends on them — and a stranger can
  reproduce both sides.
- **Say nothing and leave the documents reading "what is owed is compute".**
  Rejected, and it is the failure mode #499 exists to repair one level up. #499
  was filed because a ratified table named a closed issue as an owner, which
  reads to an outsider as discharged. Leaving "compute is owed" in place would
  be the same defect in a new costume: a reader would conclude the gap is a
  purchase order away, and would be wrong.
- **Fold this into DR-028 as an amendment rather than a new record.**
  Rejected. DR-028 is about what committed numbers may be *compared with*;
  Decisions 2 and 4 here are about what `spec/pll.md`'s Reference input row
  owes and who owns it, which is DR-019's territory and a different question.
  The overlap table does feed DR-028's Decision 4, and §Decision 5 says exactly
  how far — a cross-reference, not a rewrite of a record that is not being
  superseded.

## Consequences

- **`spec/pll.md` changes in four places and no requirement moves.** The
  Reference input summary row (row 2), the three electrical lines of the
  Reference input section, and the Verification-owed row each replace "what is
  owed there is compute, not mechanism or design" with the measured blocker and
  its owner. The requirement values, the `budget` statuses and the
  source-quality exclusion are byte-identical in substance.
- **`sim/CHARACTERIZATION.md` and `docs/chipalooza/challenge-5-proposal.md`
  carry the same correction, and the §5 verdict for this row stays
  `UNMET`.** Nothing measured moved, so nothing graded moves. What changes is
  that the reason is now true.
- **`sim/README.md`'s pin section gains the measured divergence.** DR-028's
  consequence there said the bound was owed at #549; it now additionally
  states the one measured overlap point, with the per-quantity split (delays
  inside the cross-host floor, charge far outside it) and the pointer to this
  record. Decision 3's quarantine text is unchanged.
- **`sim/harness/batch.py` no longer loses a grid to a shared ceiling.** With
  the retry, a 288-point submission survives other campaigns holding the
  fleet, which is a precondition for *any* large grid on this backend — #503
  and #533 inherit it.
- **`sim/lib/check-ref-drive-claims.sh` is untouched.** Its rule 5 fires only
  when a reference-varying deck carries a committed *record*, and under
  Decision 6 this campaign still has none. The `REARGUED` entry it will need is
  owed at the same moment the record is, and is deliberately not added ahead of
  it: an entry naming a re-argument for a record that does not exist would be
  the same kind of forward-dated claim this record declines to make.
- **#499 stays open.** Its AC 1 is undischarged, with a named mechanical
  prerequisite outside this repository rather than an open-ended one. ACs 2–4
  are discharged by DR-019 and by this record's document corrections.
- **No `2AMLogic/klayout-tools` issue is owed.** CLAUDE.md's friction protocol
  covers gaps in `klt`; this is a SPICE execution-environment and
  simulator-version matter with no layout component. Stated so a reader does
  not read the protocol as skipped.
