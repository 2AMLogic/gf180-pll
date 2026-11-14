# DR-040: The simulator init file (`set wnflag=1`) is a repository-controlled per-job input staged identically by both backends; it is part of the reference environment

- **Status**: proposed, drafting for operator ratification via PR review — the
  same route DR-039 and its predecessors record. Status stays `proposed` until
  that approval and merge. The deployment option (a, repository-controlled
  per-job initialization) was ruled by the operator on issue #755 on
  2026-10-15. The numerical equivalence tolerance, left open when this record
  was first drafted, was recorded by the testbench/spec owner on #755 on
  2026-10-22 (fleet decision 20261021-r1, D16) and is now Decision 5 below;
  the paired pilot Decision 4 owes has since been run (2026-11-14) and is
  Decision 6.
- **Date**: 2026-10-15 (amended 2026-11-14: Decisions 5 and 6)
- **Decided by**: Builder agent, issue #755 (deployment option ruled by the
  operator on the issue)
- **Revises**: DR-028 (adds a second element of the batch-versus-local
  reference environment beside the ngspice version). Nothing in DR-028 is
  rewritten and its comparison-quarantine restrictions are unchanged.

## Context

`sim/BATCH-IMAGE-DIAGNOSIS-2026-10-08.md` (Addendums 3 to 7) isolates one
simulator setting that changes the closed-loop reference state of the band-7
reference-spur deck at ff / −40 °C / 3.63 V: with `set wnflag=1` in the init
file before the netlist is read the DC solution is the reference state
(`fb` 3.63 V, no gmin stepping, −61.71 dBc, `lock_lvl` 3.63 V); without it,
the state is different (gmin stepping, `lock_lvl` ≈ 5e-9 V, −75.57 dBc). The
setting is too late inside the deck's `.control` block. The local harness and
the batch job command staged no init file, so the two backends could not
produce comparable results. The causal mechanism (per-finger model-bin
selection at parse time) is still unverified and is not claimed here.

## Decision

1. Both backends stage the same init file, `sim/harness/siminit.py`
   `INIT_TEXT` (`set wnflag=1` plus an echo of a marker line), as
   `.spiceinit` in the directory ngspice is started from, before ngspice
   starts. ngspice reads a working-directory `.spiceinit` instead of
   `~/.spiceinit`, so an ambient user or image init file is shadowed. `HOME` is
   not changed and no user file is modified.
2. The configuration is evidenced, not assumed: a point's record carries the
   init identity (`sha256:<hex>` of the staged bytes) only when the
   simulator's own output shows the marker with `wnflag=1`. Points without
   that proof are reported `unattributed` and must not be compared with
   reference-configuration points. A banner or the file's existence is not
   proof. The batch executor-environment file additionally records the
   checksum and content of the `.spiceinit` actually present on the instance.
3. A no-init negative control is retained (`stage_init=False` on either
   backend) so the known state split can be reproduced on demand.
4. This record does not change the −55 dBc requirement, DR-028's evidence
   restrictions, or authorise the 45-point grid in #533, which stays gated on
   a single-point paired pilot (ff / −40 °C / 3.63 V, `op=b7vs1p886`) matching
   the local reference including DC state and spur, under a tolerance the
   owner records. **That pilot has since been run — see Decision 6 — and this
   record still does not authorise the grid**: #533 is gated on the pilot
   *plus* its own scope decision, and the pilot's own spur result (below) is
   a reason to look at that row before spending the grid, not a clearance to
   spend it.

5. **The equivalence gate is the owner's, recorded 2026-10-22, and it is a
   measured gate rather than a fixed band.** For any local-versus-batch
   comparison of this deck:

   a. **The DC operating point is scored first.** `fb` and `lock_lvl` must
      agree. A run that settles into a different loop state fails outright,
      whatever its spur says.
   b. **Then the spur, within measured noise.** Each backend is repeated at
      least twice and the within-backend run-to-run spread is *measured*. The
      local-versus-batch difference must be no larger than that spread.
      **1 mV on the operating-point nodes and ±0.5 dB on the spur are a
      ceiling, not an allowance**: a measured spread larger than either is
      reported as a finding, never used to widen the gate.
   c. Both backends' ngspice banner, the `.spiceinit` checksum and the raw
      values are recorded with the comparison.

   The −55 dBc spec limit is **not** the equivalence criterion and may not be
   substituted for one.

6. **The pilot is run and the two backends agree exactly** (2026-11-14, ff /
   −40 °C / 3.63 V, `op=b7vs1p886`, local and batch both on the fleet's
   `ngspice-47p1` build). Full comparison, with the commands to re-derive
   every number from the committed evidence:
   [`sim/BATCH-LOCAL-EQUIVALENCE-PILOT-2026-11-14.md`](../../sim/BATCH-LOCAL-EQUIVALENCE-PILOT-2026-11-14.md).
   What it establishes is narrow and stated as such there: **this deck, this
   point, this pair of builds.** It is not a general local/batch equivalence
   result and does not relax DR-028's comparison quarantine for any other
   deck, quantity or version pair.

## Alternatives considered

- **Batch image system init file (option b)** — an external image change
  that would still need local parity and configuration provenance, and is
  less directly reproducible from this repository.
- **Setting `HOME` for the child** — works, but changes the environment the
  PDK path resolution depends on; the working-directory file achieves the
  same shadowing without it.

## Consequences

- Records taken before this change on either backend have no init identity and
  were taken in whatever state the host's ambient init file produced; they are
  not re-labelled.
- The local backend now differs from the historical invocation by one
  job-owned file in its run directory; argv, cwd, and environment handling
  are unchanged.
- Any future change to `INIT_TEXT` changes the recorded identity and needs a
  new decision record.
- **The pilot does not re-establish the −61.71 dBc figure, and must not be
  read as having tried to.** That figure (Addendum 4, run A) was taken on
  ngspice-46 against open_pdks `c6d73a35…`; the 2026-11-14 pilot runs on
  `ngspice-47p1` against the current pin `f6eeac7d…` and measures −53.513 dBc
  at the same point, in the same DC state (`fb` 3.63 V, `lock_lvl` 3.63 V, no
  gmin stepping). **Two** things moved between those two numbers — the
  simulator version and the PDK revision — so this pilot isolates neither, and
  nothing here attributes the ~8 dB to either one. What it does establish is
  that whatever moved it moved *both* backends identically, which is the
  question this record exists to answer. Quantifying the shift is a separate
  investigation and is owed before any −55 dBc verdict is read off an
  ngspice-47 record; DR-028's cross-version quarantine already forbids
  merging the two.
- **The solver is now recorded too.** A record minted after #755's harness
  change carries `solver: <name>` per point and an `Active solver:`
  provenance line, on the same abstain-rather-than-guess terms as the init
  identity. Addendum 7 measured 204 of 414 initial-solution node values
  differing between SPARSE 1.3 and KLU on this deck, so a comparison between
  two records that cannot both name their solver is not a comparison. The
  four pilot records predate that line by minutes and state their solver in
  their retained per-corner logs instead; the pilot document quotes it and
  gives the command to re-read it.
