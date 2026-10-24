# DR-040: The first committed `reference-input-contract` record is a 15/288 partial run; it restates the Reference input row and its exclusion unchanged and verifies nothing

- **Status**: proposed, drafting for operator ratification via PR review — the
  same route DR-007, DR-009 … DR-039 record. Status stays `proposed` until that
  approval and merge.
- **Date**: 2026-10-08
- **Decided by**: Builder agent, issue #680 (Doctor revision of PR #739)
- **Revises**: nothing. No ratified record and no part of `spec/pll.md` is
  edited. DR-019, DR-027, DR-035 and DR-039 stand as written.

## Context

`sim/lib/check-ref-drive-claims.sh` (rule 5) fails the tree when a campaign
whose testbench varies the reference waveform acquires a committed record,
unless a decision record that re-argues the "every number is measured against
an ideal reference" premise for that campaign is named in its `REARGUED`
table. `sim/reference-input-contract/` varies `REF` on purpose: six waveform
variants (the ideal pulse, one at each stated boundary of the Reference input
contract, and one at all three at once). Its first committed record,
`sim/reference-input-contract/records/20261008-131041-006d170.md`, trips that
rule. This record is the re-statement the check asks for, and nothing more.

That record is a **PARTIAL RUN**. Of the 288 declared points (45-point PVT grid
times six waveform variants, plus an 18-point detector-gain slice), 15 were
attempted and completed, and the batch backend then refused capacity
(`BackendError: ... no capacity in any of the 30 pools after 3 attempt(s)`).
All 15 are typical process, −40 °C, at 2.97 / 3.30 / 3.63 V. No cold fast-fast
`wedge` point ran. The grid-level criterion `min_measured_points=288` is
recorded as failed (got 15), and the 3.63 V verdict row reads FAIL because it
lacks its worst-point data. The unattempted 273 points are not evidence of
anything.

## Decision

1. **The Reference input row is restated unchanged.** The reference is the
   stated interface contract of `spec/pll.md#reference-input`: 1 – 25 MHz,
   CMOS square wave, rising-edge triggered, duty 30 – 70 %. The row stays
   **budget** for levels, edge rate and duty, and the range stays **measured**
   only as an operating condition of rows 8 and 9. The sweep that would
   discharge the budget lines remains declared and unmeasured; **this record
   does not mark any part of it verified**, and a 15/288 partial record cannot.
2. **The exclusion is restated unchanged.** Reference source quality (the
   numeric reference-jitter limit) stays excluded and unowned, as DR-019
   states it. The jitter, spur and phase-transfer figures elsewhere in this
   tree continue to rest on the ideal reference they were measured against.
   `reference-input-contract` reports no jitter and no spur number, so it
   cannot disturb that premise for the rows that do. The `20·log10(N)`
   transfer figure remains measured by `reference-phase-transfer` (DR-027).
3. **No pass criterion is relaxed.** `min_measured_points=288` and every other
   criterion in the campaign manifest stand; the record's failures are failures.
   Nothing in `spec/pll.md`, the budgets or the manifest is edited.
4. **Simulator version, stated once and unambiguously.** The record's header
   `Simulator: ngspice-42` names the binary resolved on the **recording**
   host, which ran no deck. The 15 points **executed** on `ngspice-46` on 15
   batch execution hosts, as the record's own "Executing simulator" line
   states, consistent with the image sign-off of DR-039. The record is
   generated and append-only, so its measured data and header are not
   rewritten; this decision is the clarification.
5. **The campaign is added to the check's `REARGUED` table**, naming this
   record, so the check passes by the route it prescribes and no other.

## Alternatives considered

- **Withhold the partial record until a 288/288 run exists.** Reasonable, but
  the record honestly documents a real capacity-refusal failure of the batch
  backend, labels itself partial and claims nothing. Keeping it costs nothing
  the append-only rule objects to; the guard is satisfiable with 15 points
  because this record asserts no verification.
- **Rewrite the record's header to say ngspice-46.** Rejected: evidence is
  append-only and the header is truthful about the recording host.
- **Weaken or exempt the check.** Rejected: the check says not to pass any
  other way.

## Consequences

- The row's status in `spec/pll.md` is unchanged; the owed full grid is still
  owed (#499), and a complete run needs batch capacity.
- Any later, fuller record of this campaign is a new record, not an edit.
- A reader comparing the record's `ngspice-42` header with the `ngspice-46`
  execution finds the reconciliation here and in the record's own
  "Executing simulator" line.
