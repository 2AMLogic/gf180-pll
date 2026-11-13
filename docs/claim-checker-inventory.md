# Claim-checker inventory (issue #699)

Scope ratified for #699: fold wording-only checkers together only where the
same representative mutations still fail for the same reasons. Value-grading
checkers stay functionally unchanged. This file is the inventory that gate
asks for. The `Lines` and `Commits` counts are `wc -l` and `git log` readings
taken at the commit that wrote each row; there are 18 `*/lib/check-*.sh`
scripts (the issue text said 14/15; `docs/lib/` and
`layout/lib/check-evidence-host-paths.sh` came later, and two more landed
after #699 — see "Keeping this file true" below).

## Outcome

**No checker is safely consolidable. Every script is marked KEEP, and #699's
own change shipped the inventory only (no script, test, or CI step was
altered).**

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
   so a merged script would still need one independent reader per script.
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

## Keeping this file true

**The total above and the row set below are re-derived, not remembered.**
`docs/lib/check-claim-checker-inventory.sh` enumerates `*/lib/check-*.sh` and
fails this repository's CI if the stated total differs, if a script in the
tree has no row, or if a row names a script the tree does not have. It grades
the row **set**, not its length, because the two numbers this file states were
maintained together and so agreed with each other while both were wrong:
`sim/lib/check-artifact-manifests.sh` was committed on 2026-10-23 and this
file went three weeks asserting a total of sixteen over a table of sixteen
rows while the tree held seventeen scripts.

`sim/tests/test_check_script_invocability.py` already made a new checker
impossible for CI to forget — it discovers the family from the git index and
fails on a member that is not runnable the way its own header says. Nothing
made the same promise about this file, so a checker could be wired, tested,
and absent from the one document written to enumerate the family. The same
check grades `docs/chipalooza/challenge-5-proposal.md` §5.1's count of how
many of these checkers read that document, which had gone stale the same way.

Two rows arrived with that check: the one that had been missing, and the check
itself. Neither revisits #699's ratified finding above — a later checker gets
a row and a `Decision` on the same terms as the rest.

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
| `docs/lib/check-claim-checker-inventory.sh` | 296 | this file's total and row set, and the proposal's §5.1 checker counts, vs `*/lib/check-*.sh` | tree | 1 | sixteen rows asserting a total of sixteen while the tree held seventeen | KEEP |
| `design/lib/check-port-connectivity.sh` | 274 | netlist ports vs wiring in the same file | tree | 1 | `LDT3` label misplaced; exported cleanly, port wired to `net1` | KEEP |
| `sim/lib/check-record-supersession.sh` | 221 | cited records vs supersession graph | graph | 2 | proposal described a closed FAIL as live, 18 days after the re-measurement | KEEP |
| `sim/lib/check-readme-status.sh` | 127 | README counts vs `sim/*/records/*.md` | tree | 5 | hand-written record count under-reported the tree for months | KEEP |
| `layout/lib/check-evidence-host-paths.sh` | 122 | evidence files changed vs merge base | tree | 1 | host-absolute paths in committed DRC/LVS bundles | KEEP |
| `sim/lib/check-artifact-manifests.sh` | 12 | `manifests/artifacts/*.manifest.json` vs the schema and the committed tree (logic in `check_artifact_manifests.py`, 148 lines) | tree | 1 | a manifest naming a non-`artifact:` location, or an object whose bytes are also committed | KEEP |

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
