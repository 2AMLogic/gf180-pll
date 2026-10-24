# Claim-checker inventory (issue #699)

Scope ratified for #699: fold wording-only checkers together only where the
same representative mutations still fail for the same reasons. Value-grading
checkers stay functionally unchanged. This file is the inventory that gate
asks for. Counts are `wc -l` at the commit that adds this file; there are 16
`*/lib/check-*.sh` scripts (the issue text said 14/15; `docs/lib/` and
`layout/lib/check-evidence-host-paths.sh` came later).

## Outcome

**No checker is safely consolidable. Every script is marked KEEP, and this
change ships the inventory only (no script, test, or CI step is altered).**

Reasons, in order of weight:

1. **None is a wording-only checker.** The issue's premise was that some
   scripts "only re-grade wording". Each one derives its expected value from
   something other than the graded prose: the committed tree, a netlist, a
   per-corner CSV, the spec, the issue forge, or the git merge base. Each
   fails when the prose disagrees with that source. Folding them into one
   table-driven script of exact strings would lose the derivation, which is
   the part that catches drift. The exact-string checks that do exist
   (anchored sentence fragments in a few scripts) are the *selectors* that
   locate the claim to grade, not the grading itself.
2. **Inputs barely overlap.** The shared document, the proposal, is only the
   place the claim is read. The expected side differs per script (see table),
   so a merged script would still need 16 independent readers.
3. **Mutation equivalence cannot be shown cheaply.** Each script is paired
   with a test that builds its own scratch tree fixture (about 9,000 lines of
   test code in total). A merged checker would have to reproduce every
   fixture-specific failure message to meet "same failure reason", and the
   savings would come from deleting the part that is distinct.
4. **Deliberate duplication is documented.** For example
   `check-mismatch-charge-derivation.sh` rule 2 intentionally duplicates a
   `check-quoted-value-provenance.sh` reduction, and the issue says that must
   not be de-duplicated without a stated replacement.
5. **The CI step count is not itself cost.** Separate steps give a failing PR
   a precise label; `sim/tests/test_check_script_invocability.py` already
   enforces that every `*/lib/check-*.sh` is wired and runnable, so a new
   checker cannot be forgotten.

A shared-helper refactor (for example a common "extract proposal section"
function) is possible, but it would touch value-grading scripts' code paths
and is not what the ratified scope permits; it is left to a separate issue if
anyone wants it.

## Per-checker table

"Class" is the grading kind: **value** = expected value re-derived from
evidence by computation; **tree** = expected claim derived from files
committed in the repository; **forge** = expected claim derived from the issue
tracker; **graph** = derived from the evidence supersession graph. "Commits"
is `git log --oneline -- <script>` length. Catches are taken from the WHY
sections in each script header, which record the drift each one was added to
stop.

| Script | Lines | Reads (expected side) | Class | Commits | Historical catch (from header) | Decision |
|---|---:|---|---|---:|---|---|
| `sim/lib/check-quoted-value-provenance.sh` | 3575 | proposal section 5 vs per-corner CSVs of cited records | value | 15 | quoted measurement not the number the cited record's CSVs produce | KEEP, unchanged |
| `layout/lib/check-layout-status-claims.sh` | 2321 | README/proposal vs `layout/evidence/` | tree (incl. area figures) | 16 | "No PLL block has been drawn" survived roughly five weeks after four sub-blocks landed | KEEP |
| `spec/lib/check-mismatch-charge-derivation.sh` | 1415 | `spec/pll.md` charge totals vs `sim/mc-cp-mismatch` samples | value | 4 | charge totals not reproducible from the cited Monte Carlo samples | KEEP, unchanged |
| `sim/lib/check-pvt-coverage-claims.sh` | 967 | proposal corner claims vs evidence grid | tree | 7 | worst-case at `all-fast`/`all-slow` quoted without naming the grid | KEEP |
| `design/lib/check-io-list-coverage.sh` | 846 | proposal I/O list vs `design/netlist/pll_top.spice` | tree | 2 | I/O list drifted from the exported port list | KEEP |
| `spec/lib/check-spur-derivation-arithmetic.sh` | 681 | spur derivation arithmetic in `spec/pll.md`, dBc in proposal | value | 4 | dBc figure not following from the charge total | KEEP, unchanged |
| `sim/lib/check-bias-drive-claims.sh` | 586 | proposal bias-drive text vs closed-loop decks | tree | 2 | citation of `.param iunit=8u` in a deck that has no such line | KEEP |
| `sim/lib/check-ref-drive-claims.sh` | 574 | quoted grep command vs REF-driving decks | tree | 3 | glob `*.sp` missed the `.spice` deck that varies REF | KEEP |
| `docs/lib/check-issue-reference-state.sh` | 534 | document issue references vs forge state | forge | 6 | owner issue closed while document still said "tracked at" it | KEEP |
| `spec/lib/check-spec-row-coverage.sh` | 533 | `spec/pll.md` summary rows vs proposal section 5 | tree | 4 | Reference input row absent from section 5 | KEEP |
| `sim/lib/check-record-trim-connectivity.sh` | 448 | record logs vs netlist snapshot | graph | 2 | evidence taken on an export with an unwired `LDT3` pin | KEEP |
| `sim/lib/check-characterization-coverage.sh` | 346 | `CHARACTERIZATION.md` vs `sim/*/records/` | tree | 4 | report stale by 19 records and 3 campaigns while every row existed | KEEP |
| `design/lib/check-port-connectivity.sh` | 274 | netlist ports vs wiring in the same file | tree | 1 | `LDT3` label misplaced; exported cleanly, port wired to `net1` | KEEP |
| `sim/lib/check-record-supersession.sh` | 221 | cited records vs supersession graph | graph | 2 | proposal described a closed FAIL as live, 18 days after the re-measurement | KEEP |
| `sim/lib/check-readme-status.sh` | 127 | README counts vs `sim/*/records/*.md` | tree | 5 | hand-written record count under-reported the tree for months | KEEP |
| `layout/lib/check-evidence-host-paths.sh` | 122 | evidence files changed vs merge base | tree | 1 | host-absolute paths in committed DRC/LVS bundles | KEEP |

## Notes on the closest candidates

The two smallest tree-count checkers, `check-readme-status.sh` (127) and the
aggregate-count rule inside `check-characterization-coverage.sh`, compare the
same two integers against the same `sim/*/records/*.md` enumeration. They are
the only pair with real overlap. They are not merged here because they grade
different documents (the README, and the aggregation report) and the
characterization script also owns the row-coverage rule and the reverse
direction added in #544, so merging would save well under 100 lines while
re-pairing two test suites (`sim/tests/test_sim_status_claims.py` covers both)
and the `# Usage:` invocability contract. That is a poor trade for the
verification surface, so they stay separate.
