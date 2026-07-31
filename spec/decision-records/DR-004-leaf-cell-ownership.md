# DR-004: Leaf cells in `design/` are owned, and the cell name says by whom

- **Status**: proposed
- **Date**: 2026-07-31
- **Decided by**: Doctor agent, PR #26 (issue #9), resolving issue #29
- **Scope note**: this record decides a *capture and naming* convention for
  `design/`, not an electrical parameter. It does not supersede or refine
  DR-001/DR-002/DR-003; it settles a question those records never addressed
  because there was only one block in `design/` when they were written.
- **Related**: #29 (the collision this resolves), #30 / PR #31 (the standing
  naming convention this record applies), #28 (path-independent exports,
  landed for the `pfd_cp` top in the same change)

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

`design/README.md` § "Leaf-cell ownership and naming" (landed by PR #31 for
#30) already states the standing rule: every leaf cell is namespaced
`<block-prefix>_<cellname>`, and a **bare** name is reserved for a genuinely
shared, canonical cell — with the shared-vs-per-block call recorded in a
decision record rather than made silently by reusing a filename. **This is
that decision record**, for the two cells the convention explicitly left
unresolved.

1. **The shared-cell list** — `inv_3v3`, `inv2x_3v3`, `nand2_3v3`,
   `nand3_3v3`, `nor2_3v3`, `xor2_3v3`, `tgate_3v3`, `schmitt_3v3`,
   `delaywin_3v3`, `dff_tg_3v3` **are** shared canonical cells and keep their
   bare names, at Wp/Wn = 2.5/1.0 µm, L = 0.28 µm and its ratios, exactly as
   the VCO, divider and lock detector landed them. A block satisfied by these
   instantiates them **unmodified** and never forks them. This is the list
   `design/README.md` refers to; it is not open-ended, and adding to it is
   another decision record.
2. **Block-owned cells** — a block that needs a leaf cell sized to its own
   argument owns a copy named `<block-prefix>_<cellname>`. The PFD/CP block owns
   `pfdcp_inv_3v3` (Wp/Wn = 1.5/0.5 µm, L = 0.3 µm) and `pfdcp_nand2_3v3`
   (Wp 1.5 µm, series NMOS 1 µm, L = 0.3 µm), whose sizing is a PFD
   reset-delay-and-symmetry argument, not a library default, and which carry
   full junction geometry because the chain's absolute delay is measured.
3. **A block never edits a cell another block instantiates.** Changing a shared
   library cell requires re-running and re-minting every campaign that cites it,
   under `sim/README.md`'s append-only rule.
4. **Enforced mechanically, not by vigilance.** PR #31's cross-block collision
   check is extended here to (a) compare the freshly regenerated exports rather
   than the committed ones, so a collision is caught on the run that introduces
   it, (b) refuse to *write* a colliding set, and (c) span the per-record
   `pfd_cp` top. (c) is the load-bearing addition: the committed tops already
   surface a re-sized leaf cell as a stale netlist, but `pfd_cp` has no
   committed export to diff against, so it was the one top a collision could
   pass through silently — which is exactly what happened.

`design/README.md` § "Leaf-cell ownership and naming" is the day-to-day
reference; this record is the decision it points at.

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
- **Converge both libraries on one parameterized cell** — arguably the better
  long-run end state, as #30 and `design/README.md`'s rationale both note.
  Rejected here because it reaches back into evidence already merged for the
  divider and lock detector, so it cannot be settled inside one block's PR
  without re-opening another block's results.
- **A subdirectory per block** (`design/pfd_cp/`, `design/divider/`,
  `design/lib/`) — turns the namespace collision into a path collision the
  merge surfaces loudly, which is a genuine improvement. Rejected *for now*
  only on cost: it moves every file in `design/`, rewrites every symbol
  reference and every committed export, and therefore re-mints every campaign's
  snapshot. #30's own rationale rejected it for the same reason (it ripples
  through `xschemrc`'s search path and every bare-name symbol reference for no
  benefit over a filename prefix); this record does not reopen it.
- **Do nothing and resolve each collision by hand** — this is the second
  consecutive collision on the same PR from two different block PRs, and the
  failure mode is silent. Rejected.

## Consequences

- The PFD/CP export changes bytes (`.subckt inv_3v3` → `.subckt pfdcp_inv_3v3`,
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
- Adding a fourth block means deciding, explicitly, whether it uses a
  shared-list cell or owns its own. The exporter will not let the question be
  skipped, and the shared-cell list above is now closed rather than implicit.
- If a future revision does want one converged library, it is a new decision
  record superseding this one, plus the re-run of every campaign whose cells
  move — not a quiet rename.
