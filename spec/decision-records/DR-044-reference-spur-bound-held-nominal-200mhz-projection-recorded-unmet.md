# DR-044: The Reference spur row is held at ≤ −55 dBc; the nominal corner's 200 MHz projection (−53.45 dBc) is recorded as a projected miss on the batch run, with a simulator-associated difference between the two backends recorded at that corner only

- **Status**: proposed — ratified only by operator approval of the PR that
  carries it (the two-key ceremony in `spec/README.md`). The disposition this
  record drafts — hold the bound, record the miss, attribute it via the
  control probe — was selected on issue #1061 on 2026-11-18 by that issue's
  attended `/fleet:decide` session, which auto-selected option (a) of the
  decision block under `--yolo 70` at 80% confidence (control probe first,
  then a record that states a cause) — not an operator ruling. Ratification
  stays with the operator's PR approval.
- **Date**: 2026-11-19
- **Decided by**: Builder agent, issue #1061 (disposition auto-selected by
  the issue's attended `/fleet:decide` session under `--yolo 70` at 80%
  confidence — not an operator ruling)
- **Evidence consumed**:
  `sim/reference-spur/records/20261118-212630-1649033.md` (batch, ngspice-47,
  open_pdks `f6eeac7`, minted by merged PR #1062, `Supersedes:
  20260816-132150-5f405e7`);
  `sim/reference-spur/records/20260816-132150-5f405e7.md` (local, ngspice-46,
  open_pdks `c6d73a3`, dirty tree); and the same-deck, same-PDK overlap at
  `typical_27c_3.30v_vs1p795` in
  [`sim/REPIN-DELTAS-f6eeac7-closed-loop.md`](../../sim/REPIN-DELTAS-f6eeac7-closed-loop.md)
  § "Overlap point" (local ngspice-46 control, `--no-write`, not minted).

## Context

The f6eeac7 re-qualification of `sim/reference-spur` (#828, PR #1062) moved
the `spur_dbc_200m` verdicts. The column is the measured 150 MHz spur scaled
**+2.50 dB** (`20·log10(200/150)`, arithmetic on the narrowband-FM relation,
not a measurement) to the ratified band's 200 MHz binding point, against the
unchanged −55 dBc bound:

| corner | predecessor (old) | re-run (new) | verdict |
|---|---:|---:|---|
| `typical_27c_3.30v_vs1p795` | −55.87 | **−53.45** | **PASS → FAIL** |
| `ff_-40c_3.63v_vs2p430` | −54.88 | −58.42 | FAIL → PASS |
| `sf_-40c_2.97v_vs1p677` | −54.51 | −65.69 | FAIL → PASS |

At the measured 150 MHz **all five corners pass on the batch run** (worst
−55.95 dBc, `typical`, 0.95 dB of margin; the predecessor's own worst was
−57.01). The worst
scaled point moves −54.51 → −53.45, i.e. 1.06 dB worse, and from a cold corner
to the nominal one; the nominal corner is **1.45 dB over** the bound. Direct
measurement at 200 MHz is not this record's to make: no single static band code
holds 200 MHz across the grid, which is why the binding-point campaign
`reference-spur-band-top` exists, owed at #533.

The two records differ in more than the PDK (predecessor: macOS/arm64,
ngspice-46, dirty tree; re-run: Linux, ngspice-47 on the batch fleet image,
clean tree), so #1061's 2026-11-18 decision block — auto-selected by the
attended `/fleet:decide` session — ordered a control probe before anything
was recorded. That probe re-ran the `typical` corner on the
**local ngspice-46 pin under the same `f6eeac7` PDK and the same deck**:
−62.01 dBc measured, −59.51 dBc scaled, **PASS**. Alongside the two records it
decomposes the nominal corner's movement:

| `typical_27c_3.30v_vs1p795` | measured at 150 MHz | scaled to 200 MHz |
|---|---:|---:|
| predecessor, ngspice-46, `c6d73a3` | −58.36 | −55.87 (pass) |
| local control, ngspice-46, `f6eeac7` | −62.01 | −59.51 (pass) |
| batch record, ngspice-47, `f6eeac7` | −55.95 | −53.45 (fail) |

On an identical deck and PDK the two configurations differ by **6.06 dB**
(−62.01 local vs −55.95 batch), while the PDK at fixed ngspice-46 moved the
number 3.65 dB in the opposite direction (−58.36 → −62.01). That comparison
switches more than the simulator: it goes from the **local backend** (the
ngspice-46 pin, `--backend local`, this host) to the **batch backend** (the
fleet image's ngspice-47). The nominal corner's PASS → FAIL flip is therefore
recorded as a **simulator-associated difference at that corner** — associated
with that local-to-batch switch, not attributed to the simulator alone — and
not a PDK effect and not a design change. Nothing here licenses attribution at
the other four corners: the overlap covers one corner and no other.

## Decision

1. **The Reference spur row stays at ≤ −55 dBc.** The limit, its margin and
   its budget for unmeasured mechanisms (layout parasitics, rail coupling, the
   statistical half) are unchanged. This record relaxes nothing.
2. **Each record's verdicts are scoped to its own run.** On the batch run
   (ngspice-47, `f6eeac7`) the nominal corner's 200 MHz projection is recorded
   as a **projected miss**: −53.45 dBc (−55.95 dBc measured at 150 MHz,
   +2.50 dB scaled), 1.45 dB over the bound, while its two cold corners pass
   (−58.42, −65.69). On the predecessor run (ngspice-46, `c6d73a3`) the two
   cold-corner projections fail (−54.88, −54.51). One record's passes do not
   discharge the other's misses: whether a batch-executed record may supersede
   a locally-executed one is DR-028 Decision 3(a)'s question, expressly left
   open in Decision 4 below and outside #1061. Direct verification at 200 MHz
   remains with #533, where the measured value determines whether the bound is
   met. The three verdict flips this record reports are exactly the three the
   delta tool reports for the record pair.
3. **The attribution is recorded with its reach**: at
   `typical_27c_3.30v_vs1p795` and no other corner, the flip is recorded as a
   **simulator-associated difference** between the two configurations actually
   tested — the local backend (ngspice-46 pin, `--backend local`) reads
   −59.51 dBc scaled and passes; the batch backend (ngspice-47 fleet image)
   reads −53.45 dBc scaled and fails. Both backends are named wherever this
   record states the cause, so each number can be read against the
   configuration that produced it.
4. **DR-028's cross-version comparison caveat is retained.** The overlap point
   is one corner, not an equivalence proof: it shows the batch ngspice-47
   number is not interchangeable with an ngspice-46 one for this campaign —
   the reason DR-028 Decision 3 quarantines cross-version composition, a
   quarantine DR-039 relaxed only for one other deck's `d_ref`. Whether that
   quarantine licenses the re-run's `Supersedes:` line, and any
   campaign-wide simulator-equivalence ruling, are **not decided here** (out
   of scope on #1061).
5. **No bound amendment is pre-authorized.** Any amendment of the −55 dBc
   bound — relaxing it, or accepting the miss as permanent — needs a separate
   record with an explicit operator-chosen value, the requirement DR-041
   Decision 4 attaches to an upward amendment. This requirement covers
   amendments of the bound only: a design change aimed at meeting the existing
   −55 dBc limit is a circuit change, outside this decision (#1061 scoped
   circuit changes out) and owed only its own evidence.
6. **No spec row moves, no evidence changes, no simulation is run.** This
   record adds itself only; `sim/` is untouched.

## Alternatives considered

- **Relax the bound to cover −53.45 dBc** — rejected. The ratified spec is not
  relaxed to make a projection pass (CLAUDE.md; #1061's 2026-11-18 decision
  entry says so explicitly — "The -55 dBc bound is not relaxed"), and the
  bound's unmeasured-mechanism budget has not shrunk.
- **Read the row against the ngspice-46 control numbers instead (−59.51 dBc,
  pass)** — rejected. That cherry-picks the subset that passes. The quarantine
  in DR-028 Decision 3 governs what may be *compared across versions* and, by
  Decision 3(a), which record may supersede which — a question this record
  does not answer, so neither record is designated the live evidence here.
  Both records stand with their own verdicts: the batch run projects the
  nominal corner as a miss; the predecessor's cold projections fail on its
  run.
- **Hold this record until #533 measures 200 MHz directly** — rejected on
  DR-041's reasoning. The miss is live now on committed evidence; deferring
  leaves a recorded FAIL with no disposition, which is the defect being
  repaired. This record changes no number #533 would measure.
- **Attribute the whole campaign's movement to the simulator** — rejected.
  The overlap covers one corner; DR-028's own floor analysis (several percent
  same-version, cross-host spread on neighbouring quantities) is exactly why
  one point does not license a campaign-wide claim.

## Consequences

- The row's binding-point status, scoped per run: **projected unmet at the
  nominal corner on the batch run** (−53.45 dBc, 1.45 dB over) and unmet at
  the predecessor's two cold corners on that earlier run (−54.88, −54.51).
  Each run's status is visible here rather than absorbed into a silent pass;
  which record's verdicts the row carries forward is the supersession
  question DR-028 Decision 3(a) owns and this record leaves open.
- `spec/pll.md` row 7 still cites the predecessor's figures (−57.0 dBc
  measured worst, −54.5 dBc scaled); restating that row against the re-run is
  deliberately not done in this PR (#1061 scoped the change to this record)
  and belongs to ratification or #828's campaign-wide disposition.
- #533's campaign is where direct verification at 200 MHz lands — the
  measured value there determines whether the bound is met — and it now has a
  named worst corner (`typical`) and a measured 150 MHz margin of 0.95 dB to
  scale from.
- The simulator-associated split this record records (batch ngspice-47 fleet
  image vs the local ngspice-46 pin) is a fact #828's remaining
  re-qualifications will keep meeting; each campaign's numbers stay
  quarantined from cross-version composition until an equivalence ruling
  exists.
