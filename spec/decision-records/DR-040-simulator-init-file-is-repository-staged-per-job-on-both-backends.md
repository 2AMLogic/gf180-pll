# DR-040: The simulator init file (`set wnflag=1`) is a repository-controlled per-job input staged identically by both backends; it is part of the reference environment

- **Status**: proposed, drafting for operator ratification via PR review — the
  same route DR-039 and its predecessors record. Status stays `proposed` until
  that approval and merge. The deployment option (a, repository-controlled
  per-job initialization) was ruled by the operator on issue #755 on
  2026-10-15; the numerical equivalence tolerance for the paired pilot is
  **not** set here and remains the testbench/spec owner's to record.
- **Date**: 2026-10-15
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
   owner records. That pilot has not been run by this change.

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
