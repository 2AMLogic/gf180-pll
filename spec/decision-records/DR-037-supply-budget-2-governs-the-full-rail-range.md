# DR-037: Budget 2 governs the full 2.97–3.63 V rail range; its 0.6 V figure priced half that excursion and is re-derived as 1.2 V, with the 53 mV worst-corner lock margin as the quantity that must not erode

- **Status**: proposed. The operator's ruling on #525 (2026-10-02) is the
  *input* to this record, not its ratification. Ratification goes through the
  two-key route — both RATIFY-KEY reviews, via `scripts/ratify-key.sh` in the
  `2am` repository — and the status below is changed by that route, not by the
  author of this record.
- **Date**: 2026-10-02
- **Decided by**: Builder agent, issue #525, on the operator's ruling of
  2026-10-02 (reading (a), below)
- **Relates to**: DR-021 Decisions 3, 4 and 4a (measured Budget 2 and routed
  the excursion question here — this record answers it and does not revise
  DR-021's measurement); DR-003 Decision 5 (the measured 0.9–2.7 V control
  window — unchanged, and now the second half of criterion 1b); DR-001
  Decision 2 (the predicted 0.9–2.4 V window and the eyes-open acceptance of
  supply sensitivity — unchanged); DR-012 Decision 5 (where the specification
  ratifies a value, the deck cites that value).
- **Evidence**: `sim/supply-sensitivity/records/20260925-044237-4ff4f65.md`
  and `sim/supply-sensitivity/corners/20260925-044237-4ff4f65/criterion1b_vctrl_budget.csv`
  — arithmetic on the committed 45-point grid of
  `sim/supply-sensitivity/records/20260901-155456-46b92f8.md`. **No new
  simulation, and no committed record is edited or re-judged.**

## Context

`spec/pll.md` row 12 states Budget 2 as "a DC rail excursion over
**2.97–3.63 V** must consume **≤ 0.6 V** of the Vctrl window" — a **0.66 V**
excursion. The Budget 2 derivation prices a **±10 % (±0.33 V)** excursion: a
17 % open-loop frequency shift, divided by `Kvco/f_out` spanning 0.31 … 0.84
per volt, gives 0.20 … 0.55 V, and 0.6 V was sized as that worst case plus a
small allowance (0.6 / 0.548 = 1.095). The 17 % is a half-range number: the
section's own pushing table computes it as `%/V × 0.33 V`
(−50.7 %/V × 0.33 V = 16.7 %).

Graded against the committed grid (DR-021), the two readings disagree about
whether the row is met: over the row's own 0.66 V, **9 of 15** (bundle,
temperature) cells exceed 0.6 V (worst **0.846 V** at `ss`/−40 °C, 1.41×);
over the derivation's 0.33 V, 0 of 15 do (worst 0.431 V). The measurement is
not anomalous — it matches the open-loop `f(Vctrl, vdd)` table to within
5.7 mV at every cell — so the question is which excursion the budget is
meant to bound, not whether the loop misbehaves. DR-021 Decision 4 declined to
choose, because the reading under which the result passes is one an agent may
not pick unaided. The operator has now chosen the other one.

## Decision

1. **The full rail range governs.** Budget 2 bounds the Vctrl travel over the
   whole ratified supply range, **2.97 → 3.63 V (0.66 V)**, as row 12 states
   it. The ±0.33 V half-excursion reading is **not** adopted. (Operator ruling,
   #525, 2026-10-02: reading (a).)

2. **The budget figure is re-derived for that excursion: ≤ 1.2 V.** The
   derivation is the existing one with the excursion it always specified; the
   steps are the same and only the 0.33 V → 0.66 V substitution is new:

   - Pushing is linear across the rail (`spec/pll.md`: worst departure from a
     straight-line fit 2.26 % of f_nom), so a 0.66 V excursion shifts the
     open-loop frequency by exactly twice a 0.33 V one: 2 × 17 % = **34 %**
     (exact at the worst corner: 50.7 %/V × 0.66 V = 33.5 %).
   - The loop cancels it by moving Vctrl by `0.34 / (Kvco/f_out)`. With
     `Kvco/f_out` spanning 0.31 … 0.84 per volt (unchanged):
     - high-Kvco end: 0.34 / 0.84 = **0.40 V**
     - low-Kvco end: 0.34 / 0.31 = **1.10 V**
   - The existing budget carried an allowance of 0.6 / 0.548 = 1.095 over its
     worst-case derived travel. The same allowance over 1.097 V gives
     1.097 × 1.095 = 1.20 V. **Budget 2 is ≤ 1.2 V.** (This is the old figure
     scaled by the excursion ratio, 0.6 V × 0.66 / 0.33 = 1.2 V — the number
     follows from the derivation; it was not chosen from the measured grid.)

   Cross-check, after the fact and not as an input: the worst measured cell
   consumed 0.846 V over 0.66 V, i.e. an effective `Kvco/f_out` of
   0.335 / 0.846 = 0.395 per volt, inside the 0.31 … 0.84 envelope the budget
   assumes. Measured consumption is 0.385 … 0.846 V over the 15 cells, at or
   below the derived 1.10 V low-Kvco end. (The lowest cell sits slightly under
   the 0.40 V high-Kvco end, because the derivation's 34 % shift is the
   worst-corner pushing and a cell that pushes less needs less travel.)
   **All 15 meet 1.2 V**, worst at 71 % of it (0.354 V of headroom).

3. **The miss against 0.6 V stays recorded, as an artefact of the figure and
   not a defect.** Over the full range, 9 of 15 cells exceeded 0.6 V, worst
   0.846 V (1.41×). That is a true statement about the superseded figure and is
   kept in `spec/pll.md` and in the committed records, which are not edited.
   It is not a statement that the loop, charge pump, filter or VCO is wrong:
   0.6 V was the cost of a 0.33 V excursion.

4. **The quantity that must not erode is the 53 mV worst-corner lock margin.**
   A travel budget does not by itself keep the loop in its window: 1.2 V is
   two thirds of the 1.8 V window, so a cell meeting it can still leave the
   window if the band plan places its lock point badly. What protects lock is
   the ripple peak staying inside DR-003 Decision 5's 0.9–2.7 V window, and
   its tightest measured margin is **53 mV**, at `ss`/−40 °C/3.63 V (ripple
   peak 2.647 V against the 2.7 V edge); the next tightest are +78 … +91 mV at
   the three −40 °C band-6 cells at the window's bottom. Criterion 1b grades
   both, and a change that reduces the 53 mV figure — a band-plan change, a
   VCO shift, anything that moves the consumption at `ss`/−40 °C — needs to say
   so, even while Budget 2 itself still passes.

5. **Criterion 1b of `sim/supply-sensitivity` grades the budget this record
   proposes (binding on ratification).** It
   graded DR-001 Decision 2's superseded 0.9–2.4 V prediction and never graded
   Budget 2. From the next run it grades (i) Budget 2 at ≤ 1.2 V over the
   2.97 → 3.63 V excursion, per (bundle, temperature) cell, and (ii) the
   ripple peaks against DR-003 Decision 5's 0.9–2.7 V window, reporting the
   tightest margin. The legacy 0.6 V figure is reported, informationally and
   ungraded, so the 9-of-15 history stays visible in future records.

## Alternatives considered

- **Reading (b): the ±0.33 V half-excursion governs, row 12's wording is
  corrected.** Under it the row is met at 15 of 15 cells with 28 % margin.
  Not chosen, by the operator's ruling; and it is the reading under which the
  measured result passes, which an agent may not choose unaided.
- **Keep 0.6 V over the full range and accept the 9-of-15 miss, stating the
  53 mV margin.** Rejected: 0.6 V is the answer to a different question
  (0.33 V of rail). Retaining it as a full-range gate would leave a
  specification missed by a loop that is doing exactly what the characterised
  pushing says it must.
- **Pick the figure from the measured worst case (e.g. 0.9 V).** Rejected:
  that would set the limit to fit the result. The 1.2 V figure follows from the
  derivation alone, and was compared with the measurement only afterwards.
- **Tighten supply pushing instead** (regulated VCO rail, swing-independent
  cell). These are the alternatives DR-001 Decision 2 considered and
  rejected; nothing here reopens that.

## Consequences

- Budget 2 is **met at all 15 cells** on the committed grid, with 0.354 V
  worst-case headroom against 1.2 V. That is a statement about a re-derived
  budget; the 0.6 V miss remains recorded.
- `spec/pll.md` row 12 and the Budget 2 section state one excursion (0.66 V)
  and one budget (1.2 V), and name the 53 mV margin.
- `sim/supply-sensitivity/testbench/{run.sh,report.sh}` change what future runs
  grade: criterion 1b now reads Budget 2 and the measured window. **No existing
  record is re-judged**; the `20260901-155456-46b92f8` criterion-1b FAIL stands
  as the evidence it was, classified by DR-021 and by this record. The deck
  change is exercised only by a future run, which per host policy goes through
  `klt sim` and the batch fleet (e.g. #437's trimmed-window full-grid re-take);
  none was run for this record.
- A 1.2 V budget is loose by construction: it is scaled from a budget that
  carried a 9.5 % allowance over the worst derived travel. Its protective value
  is thereby carried by the window margin of Decision 4, not by the number
  itself.
- **Not addressed here:** the passive process axes (C1 spans 107.1–133 pF over
  corners, DR-006; every input is pinned `res_typical`/`moscap_typical`/
  `mimcap_typical`), and the 10 of 45 grid rows still converging when sampled
  (#437). Either could move consumption and the 53 mV figure.
