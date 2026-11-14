# Roadmap

gf180-pll is an integer-N ring-oscillator PLL for the `gf180mcuD` open PDK, built by agents in the
open flow (xschem, ngspice, klayout-tools) with every claim backed by a committed evidence record.

Status as of 2026-11-13, `main` @ `658a7fdf`.

This page says what comes next and why. It does not restate status: the machine verdict is
[`signoff/tier-report.json`](../signoff/tier-report.json), the campaign detail is
[`sim/STATUS.md`](../sim/STATUS.md) and the layout detail is
[`layout/STATUS.md`](../layout/STATUS.md). Where this page and those disagree, they win.
`WORK_PLAN.md` is the generated label-state view; the tracker for the gap to T1 is #127.

## Where it stands

- **Spec.** `spec/pll.md` is ratified with amendments; Lock time (row 9) and Lock detector (row 16)
  are carved out and unratified. DR-037 (supply budget), DR-038 (output-band ceiling) and DR-042
  (loop-filter C2 device) are `proposed`, not ratified.
- **Simulation.** 108 evidence records across 27 campaigns (`sim/STATUS.md`). Closed-loop lock is
  not shown across PVT: `lock-time` passes 21/135 cold-start rows, `output-range` 0/45. Period
  jitter: deterministic part at 45/45 corners, random part bounded (DR-032, DR-033). Reference spur:
  5/45 corners at 150 MHz; neither 200 MHz band-top campaign has a measured record.
- **Harness migration.** `loop-dynamics` reproduces its baseline on the batch backend (PR #903,
  pilot GO). `output-range` ran its full 90-row grid there (PR #909): 83/90 measured, NO-GO against
  the proposed tolerances.
- **Layout.** All four sub-blocks are drawn, DRC-clean and LVS-matched on the foundry decks
  (generated table in `layout/STATUS.md`). The assembled `pll_top` GDS is committed with one
  inherited DRC violation (`MIMTM.3` on the loop filter's C2), no top-level LVS, and 0.4078 mm²
  against the ratified 0.30 mm² area row (DR-041 holds the row and records the miss).
- **PDK pin.** The repo is on open_pdks `f6eeac7` (#789). The records the reader-facing documents
  cite were measured under the previous pin and are being re-qualified (#790).
- **T1 evidence ladder** (`klt signoff`, klayout-tools 0.8.0): **6 of 22 rows met** — items 1, 9 and
  10 on both partitions.

| T1 item | Verdict | What is missing |
|---|---|---|
| 1 Design sources | met | — |
| 2 Layout | unmet | no artifact-anchored envelope cited for the block GDS |
| 3 DRC clean | unmet | block-level clean report; `MIMTM.3` (#753, then #149) |
| 4 LVS clean | unmet | top-level LVS has not run (#149) |
| 5 Corner verification vs ratified spec | unmet | rows 9 and 16 unratified; evidence is not in `klt sim` envelope form |
| 6 Monte Carlo evidence | unmet | see `signoff/README.md`, "Item 6" (klayout-tools#2531) |
| 7 Post-layout verification | unmet | needs a clean block layout to extract (#18) |
| 8 Characterization report | unmet | `sim/CHARACTERIZATION.md` exists but is uncited (#843) |
| 9 Testbenches shipped | met | — |
| 10 Repo hygiene | met | — |
| 11 Power delivery | unmet | `klt erc` on `pll_top` is clean; the paired block-level `klt lvs` envelope does not exist |

## Now

1. **Option-B C2: physical checks first (#753).** Run the unmodified variant-D DRC and LVS on the
   option-B loop filter, with the opened-link control, before any grid is launched (DR-042 Decision
   4; the ruling on #753 sets this order). *Done when* the DRC and LVS logs and an updated
   `PROOF.md` are committed under `layout/evidence/loop-filter-layout/`, stating clean or naming
   each violation. This is the item everything in layout signoff waits on.
2. **Re-qualify the device-characterization records under `f6eeac7` (#825).** In progress. *Done
   when* the five cited records each have a successor record naming what it supersedes, with an
   old-versus-new delta table.
3. **Land the open clean-up PRs.** #919, #920 and #921 (for #916, #915, #918) and #917. *Done when*
   merged with CI green.
4. **Make the README's T1 count match the report.** `README.md` still says "0 of 22 rows met"; the
   report says 6. *Done when* the sentence is corrected and a CI check fails when the README's count
   differs from `tier-report.json`. No issue yet.
5. **Correct the "no `klt drc` / `klt lvs` envelope exists" statements.** `signoff/README.md` and
   `layout/README.md` predate the envelopes committed under
   `layout/evidence/vco-layout/klt-curated-836*/` and
   `layout/evidence/pll-top-layout/klt-curated-836/`. *Done when* both files describe what is
   committed and why it is still uncited. No issue yet.
6. **`klt lvs` envelope for `lock_detector`.** Only `vco_block` has one (`klt-curated-836-recheck/`,
   `status: match`). *Done when* a request, report and `RECORD.md` are committed under
   `layout/evidence/lock-detector-layout/`, whatever the verdict, with any tool gap filed on
   klayout-tools. No issue yet.

## Next

- **Formal block-level DRC and LVS reports for `pll_top` (#149)** — after #753 clears `MIMTM.3`.
  Done when both reports are committed and items 3 and 4 can be cited.
- **Post-layout extracted re-run of the verification suite (#18)** — after #149. Done when
  extracted-netlist records sit beside their schematic baselines with deltas stated (item 7).
- **Remaining re-qualification groups (#826, #827, #828)** — after #825; then #829 cites the new
  records and regenerates the sign-off; then #843 cites `sim/CHARACTERIZATION.md` for item 8; then
  #790 and #788 close.
- **`klt lvs` envelopes for `pfd_cp` and `divider_chain`** — after Now 6 shows the recipe carries
  over. With all four, item 11's pairing has its sub-block half.
- **`mc-cp-mismatch` harness migration (#879)** — after #878 is closed out.
- **C2 electrical validation (#753, second stage)** — `devchar-passives` for the option-B MIM and
  the 140-cell `loop-dynamics` grid, after stage one is clean and the simulator on the workers can
  load this repo's decks.
- **200 MHz band-top campaigns (#503, #533)** — after #755 gives matching pilots on both backends.
  Done when each has a 45-point record.
- **Reference input contract (#499)** — after #680.
- **Post-supply-step re-lock campaign (#405, #395)** — after the simulator blocker below.

## Later

- **Sustained lock across PVT.** Is the `lock-time` shortfall a test window that is too short, or
  the loop? Rows 9 and 16 stay unratified until measured. `sim/STATUS.md` also lists measurements
  left unowned when #399, #437 and #540 closed; they need refiling with a scope.
- **Area.** Which levers from `layout/evidence/pll-top-layout/area-feasibility/` are worth drawing
  to move 0.4078 mm² toward the 0.30 mm² row?
- **Lock-detector trim on silicon.** DR-022 finds the trim rule executable only in simulation on
  this die; what observable would make it executable at test?
- **Items 5 and 6 as `klt` envelopes.** Does migrating campaigns to harness manifests yield
  envelopes `klt signoff` can grade, and does the cross-version quarantine of DR-028 allow them to
  be cited (#549)?
- **5.0 V analog rail.** The Chipalooza proposal records that the design is 3.3 V-only; is a 5.0 V
  variant in scope at all?

## Blocked and waiting

- **Simulator version.** #680, #755 and #405 are parked because the simulator now on the workers and
  the batch image fails at netlist load on this repo's MOS-capacitor instances (recorded on #755 and
  #680). Every grid campaign above waits on a matched simulator pair across both backends.
- **Operator decisions pending:** how #878 closes out given the NO-GO record; where the simulator
  init file is supplied (#755, DR-040); how the two band-top campaigns proceed after their pilots
  disagreed with the local run (#533, #503); the README chart source (#479).
- **Ratification pending:** DR-037, DR-038 and DR-042 are `proposed`.
- **Held:** PR #739 (partial reference-input-contract record), PR #911, #861 (CodeQL flake).

## Not planned

- A hand-maintained T1 checklist: the report is the verdict.
- Relaxing a ratified spec row to make a result pass; a miss is recorded and a decision record is
  written.
- Silicon measurement: `measurements/` stays empty until there is silicon.
