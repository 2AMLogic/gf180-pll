# DR-026: The lock-detector trim MSB was unconnected at `pll_top` — what the `ff` cell measured, what is withdrawn, and what a connectivity claim now has to survive

- **Status**: proposed, drafting for operator ratification via PR review — the
  same route DR-007, DR-009 … DR-025 record (a builder drafts the record on the
  evidence; the operator's PR approval is the ratifying act). Status stays
  `proposed` until that approval and merge.
- **Date**: 2026-09-25
- **Decided by**: Builder agent, issue #515
- **Numbering**: DR-026 is the next unused slot as of `1937f52`, where the
  highest on `main` is DR-025. TEMPLATE.md's collision rule requires this
  re-check immediately before opening the PR and again after any rebase onto a
  moved `main`. **Open PR #535 carries a record numbered DR-024**
  (`DR-024-reference-phase-transfer-measures-the-exclusions-transfer.md`),
  which already collides with `main`'s DR-024 and has not rebased; whichever
  of that PR and this one merges second must run the re-check again.

## Context

**A declared port was never wired, and nothing in this repository could see
it.** `design/lock_detector.sym` places the `LDT3` trim pin at symbol-relative
`(−70, −60)`, above `UP`, while `LDT0`–`LDT2` sit below `DN` at
`(−70, +20/+40/+60)`. `design/pll_top.sch` instantiated `XLD` at `(300, 900)`
and placed all four trim labels as if the run continued below `LDT2`
(`y = 920, 940, 960, 980`). Three landed on a pin. `l_XLD_LDT3` at
`(230, 980)` landed on empty canvas, and the real pin at `(230, 840)` stayed
open. xschem exported the open terminal under an auto-generated name, so
`.subckt pll_top` declared an `LDT3` port that nothing inside it read, and
`XLD`'s eighth argument read `net1` — an auto-named net with exactly one
connection in the whole file.

The consequence is arithmetic: **the detector saw `code & 0b0111`.** Eight of
the sixteen window trim codes were unreachable on the assembled part, and a
deck programming one of them ran at the code eight below it.

`spec/pll.md`'s normative
[Lock-detector window trim-code rule](../pll.md#lock-detector-window-trim-code-rule)
selects **code 11** (`1011`) for the `ff`/`all-fast` bundles — a code whose MSB
is exactly the bit that came loose. DR-015 verified that `LDT0`–`LDT3` exist as
`pll_top` **ports**; nobody checked they were **connected**, and no check in
this repository could have. `design/netlist.sh --check` re-exports every
schematic and diffs: it reported all seven netlists clean, correctly, because
the export was internally consistent with the broken schematic — there was
nothing to diff against. `design/lib/check-io-list-coverage.sh` (#237) grades
whether a port is *named* in the Chipalooza pad table, not whether it is
*wired*, and `LDT3` had every right to its row.

**One committed record programmed a code with its MSB set.**
`sim/supply-sensitivity/records/20260920-180604-0f91a9b.md` (#417) is the
run `spec/pll.md`'s Lock detector row cites to discharge DR-013 Decision 4's
item (b): the window-vs-offset crossing measured **inside one closed loop**
rather than inferred across two campaigns, at the two cells DR-013 names. Its
`typical`/−40 °C cell is at code 7 (`0111`); its `ff`/27 °C cell is described
as code 11.

`sim/supply-sensitivity/records/20260925-111906-1937f52.md` re-examines that
record's own committed logs and establishes what the `ff` cell actually ran at.
It re-simulates nothing.

## Decision

**1. The ratified Lock detector row's targets are not relaxed, cornered, or
given an exception.** T1′ and T2′ stand exactly as ratified, and the
[Lock-detector window trim-code rule](../pll.md#lock-detector-window-trim-code-rule)
stands exactly as written — including code 11 for `ff`/`all-fast`. Nothing
below narrows a bound; it narrows what the *evidence* is entitled to say.

**2. The `ff`/27 °C/3.63 V crossing verdict is withdrawn as a statement about
code 11, on measurement.** The re-examination establishes, from two
independent readings of committed artifacts, that the loop ran at **code 3**
(`0011`), not code 11:

- **The node dump.** All five `ff` logs print the `ldt3` pad at the rail
  (2.97 / 3.30 / 3.63 V) and `xdut.net1` at 0 V in the same DC operating-point
  table. `grep -rl 'ldt3_code=1' sim/*/corners/*/` returns exactly those five
  logs across the whole repository.
- **The window comparison, which discriminates.** At `ff`/27 °C/3.63 V the
  settled offset is 1.2331 ns. `sim/lock-window-trim`'s committed 1872-point
  code map measures `t_win` at that same (bundle, temperature, supply) as
  1.3015 / 1.2801 ns at **code 11** and 0.9865 / 0.9721 ns at **code 3**.
  Under the one-sided bound `window_crossing.csv`'s own header states — the
  observable window is never smaller than `t_win` — code 11 predicts the flag
  **asserts**. It did not. Code 3 puts the window 0.25 ns below the offset,
  under which a non-assert is what is expected.

The recorded row is therefore a true observation **at code 3**, where
`at-or-below` is what the map predicts, and it says nothing about the
rule-selected code. `sim/README.md`'s append-only rule means the record stands
exactly as taken; what is corrected is the description of the configuration it
was taken under.

**3. DR-013 Decision 4's item (b) is discharged at `typical`/−40 °C/3.63 V
only, and the withdrawal is not neutral.** Code 7's MSB is clear
(`7 & 0b0111 = 7`), so that cell ran at the code its record states and its
`above` / **confirmed** verdict stands unchanged. At the `ff` cell, the same
code map puts code 11's window **above** the offset — which under
`window_crossing.csv`'s own verdict key would make the cell **`moved`** (the
window is above the offset where DR-013 had it below) rather than
`confirmed`. This record does **not** assert that outcome: the predicted
margin is +0.068 / +0.047 ns (5.5 % / 3.8 %) and the map is taken at
f_ref = 25 MHz against the loop's 12.5 MHz. It asserts that the question is
**open**, and that a cell whose verdict may reverse may not be carried as
discharged.

**4. The re-take is owed at #437, and must run on a post-fix netlist.** #437
is the declared trimmed-window **full-grid** re-run of `sim/supply-sensitivity`
and already owns the coverage residual against this row; the `ff`/27 °C cell is
a subset of it. `run.sh`'s transcription of the rule maps `ss`/`all-slow` → 3,
`fs` → 6, `ff`/`all-fast` → 11, `typical`/`sf` → 7, so exactly one of the five
bundles carries an MSB-set code: **3 of the 15 (bundle, temperature) cells, 9
of the 45 points**. A re-run taken on the pre-fix export would corrupt all
nine silently and would have to be discarded.

**5. A connectivity claim about `pll_top` is now a mechanically checked claim,
not an inspection result.** `design/lib/check-port-connectivity.sh` runs in CI
over every committed `design/netlist/*.spice` and fails on either of two
conditions: a port declared by a file's own top-level `.subckt` that no
instance line inside that subcircuit's body connects to, or an xschem
auto-named `net<N>` anywhere in the file with exactly one connection. It
reproduces this defect against the pre-fix `design/netlist/pll_top.spice` and
passes against all seven post-fix netlists. The check is the decision: "the
ports are wired" is not a statement this repository will accept again on the
strength of a port list.

**6. The fix is in the schematic, at the label, and the symbol is unchanged.**
`l_XLD_LDT3` moves from `(230, 980)` to `(230, 840)`, the `LDT3` pin's actual
absolute position for an `XLD` instantiated at `(300, 900)`.
`design/lock_detector.sym` is **not** touched. Moving the pin instead would
have changed every instantiating schematic and every symbol-relative
coordinate downstream of it to fix one label; moving the label changes one
line and one netlist argument, and `./design/netlist.sh --check` is clean
after it.

## Alternatives considered

- **Move the `LDT3` pin in `design/lock_detector.sym` to `(−70, +80)` so the
  trim pins form one contiguous run** — rejected for this change, though it is
  the more legible symbol. It edits a symbol every instantiating schematic
  places, so every one of them would need its labels re-checked in the same
  commit as a defect fix, and a fix whose blast radius is larger than the
  defect is the wrong shape of fix. The symbol's pin order in
  `.subckt lock_detector` is unchanged by either choice, so nothing downstream
  of the netlist depends on which was picked. If the symbol's layout is
  revisited later, this record does not stand in the way — it records that the
  *wire* was the defect, not the pin's position.
- **Re-take the `ff` cell in this change and report a corrected verdict** —
  rejected on compute, not on merit. The re-take is three fresh closed-loop
  transients (~1 h each at this corner on the committed deck), and #437
  already owns that campaign's re-run and is labelled `loom:operator-only` for
  exactly this reason. Withdrawing a verdict this change can prove wrong,
  while naming the owner and the prerequisite, is honest; carrying it as
  discharged until someone has compute is not.
- **Edit `20260920-180604-0f91a9b.md` to say "code 3"** — rejected outright.
  `sim/README.md`'s append-only rule forbids it, and it would be wrong on the
  merits as well: the record truthfully states the code the deck *programmed*.
  The correction belongs in a successor record and in this file.
- **Strengthen `check-io-list-coverage.sh` instead of adding a second check** —
  rejected. That check grades a *document* (the Chipalooza pad table) against a
  netlist's port list; this one grades a netlist against *itself*. Folding a
  connectivity rule into a documentation-coverage check would make a failure
  ambiguous about which artifact is wrong, which is the property that makes
  either check actionable.
- **Rely on `design/netlist.sh --check`** — not available. It diffs a
  re-export against the committed netlist and is therefore blind by
  construction to a schematic that is wrong in a way that exports cleanly.
  It reported this tree clean throughout.

## Consequences

- **`spec/pll.md`'s Lock detector row loses one of the two cells it cites as
  discharging DR-013 Decision 4 item (b).** The row now states the `ff` cell as
  withdrawn pending a re-take at #437, with the direction the committed code
  map predicts stated rather than hidden. The `typical` cell is unchanged.
  This is a **reduction in what the evidence is claimed to support**; no target
  moves.
- **The verdict may reverse.** If the re-take asserts at code 11, the `ff` cell
  becomes `moved` and DR-013's inference at it is contradicted rather than
  confirmed. DR-013 Decision 4's "marginal observer at two corners and a wrong
  one at one" would then rest on one in-loop cell, not two, until #437 lands.
  That is a worse evidentiary position than the row claimed this morning, and
  the row now says so.
- **#437 gains a hard prerequisite.** Its re-run is only valid on a netlist at
  or after this change. The nine `ff` points of the 45-point grid would
  otherwise be corrupted identically and silently.
- **#527's stated blocker is discharged.** `spec/pll.md`'s Lock detector row
  item (e) recorded both candidate routes to executing the trim rule as
  "blocked behind #515, which leaves `LDT3` unconnected at `pll_top` so only 8
  of the 16 codes are reachable". All 16 are reachable now. #527's own merits
  — whether a symmetric `REF` phase-step bisection read at `LOCK` selects the
  code to the accuracy the row's 1.53–1.58× spread figure assumes — are
  untouched by this record, and **DR-022's finding stands in full**: nothing
  here gives the trim rule an executable route, it only removes an obstacle
  that would have defeated one.
- **Every `pll_top`-level result taken before this change is now cheap to
  audit**, and has been: `grep -rl 'ldt3_code' sim/*/corners/*/` and
  `grep -rl 'xdut.net1' sim/` both return the ten logs of one record, so the
  blast radius is bounded to the cell this record withdraws. `sim/lock-detector`
  and `sim/lock-window-trim` drive `lock_detector` / `delaywin_3v3` directly,
  never through `pll_top`, so the 205-point re-characterization and the
  1872-point code map — the evidence T1′/T2′ actually rest on — never passed
  through the missing wire and are unaffected.
- **A new class of defect is now caught in CI, and it is a class, not this
  instance.** Any future schematic edit that drops a label off a pin leaves the
  same signature — a declared port with no reader, or a single-connection
  `net<N>` — in any of the seven committed netlists, not only `pll_top`. The
  cost is one more CI step reading committed text; it opens no PDK and invokes
  no simulator.
- **What the check still cannot catch, stated rather than implied**: a port
  wired to the *wrong* pin rather than to nothing. Both of this check's rules
  are satisfied by a mis-wired net that has two connections. That class remains
  the responsibility of `check-io-list-coverage.sh`, of review, and of the
  recorded evidence in `sim/`.
