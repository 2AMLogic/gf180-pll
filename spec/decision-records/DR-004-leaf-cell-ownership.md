# DR-004: Leaf cells in `design/` are owned, and the cell name says by whom

- **Status**: proposed
- **Date**: 2026-07-31
- **Decided by**: Doctor agent, PR #26 (issue #9), resolving issue #29
- **Scope note**: this record decides a *capture and naming* convention for
  `design/`, not an electrical parameter. It does not supersede or refine
  DR-001/DR-002/DR-003; it settles a question those records never addressed
  because there was only one block in `design/` when they were written.
- **Related**: #29 (the collision this resolves), #30 (the structural
  follow-up), #28 (path-independent exports, landed for the `pfd_cp` top in the
  same change)

## Context

`design/` is a flat namespace and every block PR authors the static-CMOS leaf
cells it needs directly into it. With three blocks landing in parallel this
produced two *different* cells under the same filename:

| Cell | PR #26 (PFD/CP) | PR #27 (divider + lock detector), merged first |
|---|---|---|
| `inv_3v3` | Wp/Wn = 1.5/0.5 µm, L = 0.3 µm (3:1) | Wp/Wn = 2.5/1.0 µm, L = 0.28 µm (2.5:1) |
| `nand2_3v3` | Wp 1.5 µm, series NMOS 1 µm, L = 0.3 µm | Wp 2.5 µm, series NMOS 2 µm, L = 0.28 µm |
| device cards | full `ad/pd/as/ps/nrd/nrs/sa/sb/sd`, `spiceprefix=X` | `W/L/nf/m` |

Git reports this as an `added in both` conflict, but the dangerous property is
what happens *after* it is resolved: whichever definition survives silently
becomes the definition for the other block too, and every tool still reports
success. `design/netlist.sh` already documented the mechanism ("each carries
its own copy of the shared leaf cells … including two would redefine them")
without preventing it.

The stakes are not symmetric with a normal naming argument. `inv_3v3` is the
delay element of the PFD's 24-inverter reset chain, whose *absolute* delay is
the load-bearing parameter behind the dead-zone result in
`sim/pfd-deadzone/` — a 6-inverter chain measurably failed 9 of 45 corners.
Adopting a 2.5:1 gate at minimum length in that chain changes the number the
result rests on. In the other direction, re-sizing the divider's gates would
invalidate the 465-run evidence already merged for #11.

## Decision

**A leaf cell in `design/` belongs to exactly one owner, and its name states
the owner.**

1. **Shared logic library** — `inv_3v3`, `inv2x_3v3`, `nand2_3v3`,
   `nand3_3v3`, `nor2_3v3`, `xor2_3v3`, `tgate_3v3`, `schmitt_3v3`,
   `delaywin_3v3`, `dff_tg_3v3` are unowned, general-purpose cells at
   Wp/Wn = 2.5/1.0 µm, L = 0.28 µm and its ratios. A block that is satisfied by
   these instantiates them **unmodified** and never forks them.
2. **Block-owned cells** — a block that needs a leaf cell sized to its own
   argument owns a copy named `<block>_<cell>`. The PFD/CP block owns
   `pfd_inv_3v3` (Wp/Wn = 1.5/0.5 µm, L = 0.3 µm) and `pfd_nand2_3v3`
   (Wp 1.5 µm, series NMOS 1 µm, L = 0.3 µm), whose sizing is a PFD
   reset-delay-and-symmetry argument, not a library default, and which carry
   full junction geometry because the chain's absolute delay is measured.
3. **A block never edits a cell another block instantiates.** Changing a shared
   library cell requires re-running and re-minting every campaign that cites it,
   under `sim/README.md`'s append-only rule.
4. **The convention is enforced mechanically, not by vigilance.**
   `design/netlist.sh` fails the run if any `.subckt` name is defined by both
   the per-record `pfd_cp` export and a committed top. For the committed tops
   `--check` already catches a re-sized leaf cell as a stale netlist; the
   per-record top had no such gate, and that was the silent hole.

`design/README.md` states the convention (§ Leaf-cell ownership) and is the
day-to-day reference; this record is the decision behind it.

## Alternatives considered

- **Adopt the merged (#27) `inv_3v3`/`nand2_3v3` for the PFD as well** — one
  canonical logic library today, and the option with the cleanest end state on
  paper. Rejected for this change because it is not a rename: it re-sizes the
  reset chain the dead-zone result depends on (faster gates → shorter reset
  delay → the pump-turn-on race that failed 9 of 45 corners), it drops the
  junction geometry that chain's absolute delay is measured with, and the
  sizing argument in `design/README.md` plus the mismatch budget would have to
  be **re-derived**, not merely re-run. That is a design revision, and a
  conflict resolution is the wrong vehicle for one.
- **Converge both libraries on one parameterized cell** — the best end state,
  and the direction #30 records. Rejected here because it reaches back into
  evidence already merged for the divider and lock detector, so it cannot be
  settled inside one block's PR without re-opening another block's results.
- **A subdirectory per block** (`design/pfd_cp/`, `design/divider/`,
  `design/lib/`) — turns the namespace collision into a path collision the
  merge surfaces loudly, which is a genuine improvement. Rejected *for now*
  only on cost: it moves every file in `design/`, rewrites every symbol
  reference and every committed export, and therefore re-mints every campaign's
  snapshot. Left open under #30, which this record does not foreclose.
- **Do nothing and resolve each collision by hand** — this is the second
  consecutive collision on the same PR from two different block PRs, and the
  failure mode is silent. Rejected.

## Consequences

- The PFD/CP export changes bytes (`.subckt inv_3v3` → `.subckt pfd_inv_3v3`,
  and instance lines to match) with **no electrical change whatsoever**: the
  regenerated export is byte-identical to the previous snapshot once the rename
  is undone and path comments are normalized. The `sim/pfd-deadzone/` and
  `sim/cp-compliance/` records are nonetheless re-minted under new IDs, because
  `sim/README.md` forbids editing a record's cited netlist hash in place. The
  re-minted records state the supersession is provenance-only and carry the
  re-measured values, which reproduce the originals.
- The divider, lock detector and VCO are untouched: their committed exports
  still pass `design/netlist.sh --check` byte for byte, and no record of theirs
  moves.
- Two nominally similar inverters now exist in `design/`. That duplication is
  the accepted cost, and it is visible rather than latent — previously the
  duplication existed too, it was just hidden behind one filename.
- Adding a fourth block means deciding, explicitly, whether it uses the shared
  library or owns its cells. The exporter will not let the question be skipped.
- If a future revision does want one converged library, it is a new decision
  record superseding this one, plus the re-run of every campaign whose cells
  move — not a quiet rename.
