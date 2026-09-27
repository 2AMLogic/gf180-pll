# DR-034: The reference-spur charge stack is re-priced at the widened 21-point corner axis — term 3 is **5.56626 fC**, the derived spur rows move, term 1 keeps **±20 %**, and DR-018's "≥ 1.5 dB inside the line" selection rule is retired as unsatisfiable rather than met

- **Status**: proposed — drafted on committed evidence by a builder; the
  operator's PR approval is the ratifying act, the same
  ratification-via-PR route DR-007, DR-009 … DR-018 and DR-024 record. Status
  stays `proposed` until that approval and merge. `spec/pll.md`'s
  charge-accounting table and `design/README.md`'s mismatch-budget section are
  *downstream* of this decision and are updated in the same commit, which is
  the position DR-016 and DR-018 were both in when they filed `proposed`.
- **Date**: 2026-09-27
- **Decided by**: Builder agent, issue #610 (successor to the measurement in
  PR #609 / issue #597)
- **Relationship to DR-018**: **partial supersession, stated part by part**, in
  the same shape DR-018 itself used for DR-006 §8. DR-018 stays `proposed` and
  its central decision stands: term 1's budget is **±20 %** and the ratified
  reference-spur line **≤ −55 dBc** does not move. What this record replaces is
  narrower and is named exactly:
  - DR-018 §Context's term-3 Input row (4.25246 fC, from the 3-point corner
    axis) — **re-priced** here at 5.56626 fC.
  - DR-018 §Context's derived arithmetic downstream of that row — the 7.933 fC
    two-term sum, the 6.073 fC leftover, the **32.6 %** ceiling, and the
    dBc column of its term-1 table — **all re-derived** here.
  - DR-018 §Decision 2's *selection rule* ("the largest 5 %-granular value that
    keeps the conservatively stacked derivation at least 1.5 dB inside
    −55 dBc") — **retired**, because at the widened axis no 5 %-granular value
    satisfies it *and* covers the measurement (§Decision 3). ±20 % survives on
    a different, stated basis.
  - DR-018 §Decision 5's fail-loud numbers (the 6.07 fC allocation, the 32.6 %
    ceiling) — **restated** at the new figures.

  Everything else in DR-018 — §Decision 1 (the ±20 % budget itself),
  §Decision 3 (which statistic term 1 is checked as), §Decision 4 (what ±20 %
  does not cover), its Alternatives, and Amendment A1 — is untouched and
  remains the reason ±20 % is the number. DR-018's own bytes are not edited:
  its 4.25246 fC was a true reduction of the evidence it cited, and stays
  readable as that.

## Context

`spec/pll.md`'s [Reference spur](../pll.md#reference-spur) derivation carries a
charge-accounting table that DR-018 built to price the ratified ≤ −55 dBc line
against the charge-pump terms `sim/mc-cp-mismatch` measures. One of its
ingredients is the **statistical residual net charge** — the mismatch budget's
term 3, the per-reference-cycle net charge at zero phase error, reduced as the
worst corner's `|mean| + 3σ`. DR-018 priced it at **4.25246 fC**, the worst of
the **3** corner points that campaign visited when the record was written
(`typical`/27 °C/3.30 V, `ss`/125 °C/2.97 V, `ff`/−40 °C/3.63 V).

PR #609 (issue #597) widened that campaign's corner axis to **21** points —
nominal plus all 20 vertices of the process × temperature × supply box, with
the MOS-bundle axis swept in full, so `fs` and `sf` are measured for the first
time in this campaign. Record:
`sim/mc-cp-mismatch/records/20260927-102154-d004d5b.md`. Term 3's worst corner
moved to `sf`/125 °C/3.63 V — a newly visited mixed bundle — and reads
**5.56626 fC**, +1.31 fC over the figure DR-018 priced. That record's own
re-grading table separates the two things that changed between the two
campaigns: +0.416 fC of it is the execution host (the same corner,
`ff`/−40 °C/3.63 V, on two machines) and +0.898 fC is the corner axis.

Term 3's own budget is ±20 fC, and 5.56626 fC uses 27.8 % of it, so **no
verdict in `design/README.md`'s mismatch table changes** — all four terms
still PASS at the wider axis. What changes is an input to a derivation the
ratified spur row is read against, which is why the campaign record
deliberately did not touch the stack and routed it here.

### Every ingredient, re-derived from committed evidence

Each figure below is a reduction of a committed CSV, not a restatement of
DR-018's table. `spec/lib/check-mismatch-charge-derivation.sh` performs all
five reductions in CI; the parenthetical after each is what that check prints.

| Input | Value | Source | Reduction |
|---|---|---|---|
| Statistical residual net charge (term 3), corner-combined \|mean\|+3σ, 21 corners | **5.56626 fC** (worst `sf`/125 °C/3.63 V) | `sim/mc-cp-mismatch/corners/20260927-102154-d004d5b/mc_pfd_cp.csv` | per corner `\|mean\| + 3·sd` on `qnet0_c`, worst corner kept |
| Term 1, DC UP/DN mismatch, signed \|mean\|+3σ, 21 corners | 17.0863 % (worst `sf`/−40 °C/3.63 V) | same record's `mc_cp_dc.csv` | worst-magnitude of the three Vctrl points per (corner, seed), then per corner `\|mean\| + 3·sd` on the **signed** series |
| Systematic per-event charge asymmetry \|q_up + q_dn\|, 45 corners | 3.67840 fC (worst `fs`/125 °C/3.63 V) | `sim/cp-compliance/corners/20260802-061841-c24ee3a/cp_switch.csv` | \|`qup_c` + `qdn_c`\| per (corner, Vctrl) point, worst kept (median 2.15650 fC) |
| `Icp`, largest trim code (11, four unit legs), 45 corners | 6.71411 – 7.20923 µA (worst `ff`/125 °C/3.63 V) | `sim/cp-compliance/corners/20260801-190821-734f483/cp_dc.csv` | mean of the two polarities at Vctrl = 1.65 V, min/max across every corner |
| Reset overlap `T_ov`, min UP/DN pulse at zero phase error, 45 corners | 1.11328 – 2.58390 ns (worst `ss`/125 °C/2.97 V) | `sim/pfd-deadzone/corners/20260916-051356-8cedbba/raw_measures.csv` | smallest UP/DN pulse over the corner's control-voltage points |
| C2, worst-case minimum over corners | 1.814 pF | DR-006 Decision 1 | — |
| TIE per unit ripple | 0.669 ps at 1.825 mV | DR-006 §8 / `sim/loop-dynamics` §7 | — |

The two Monte Carlo rows' own dispersion, for readers weighing the figures
against sampling noise: term 3's binding corner has mean −3.31116e-15 C and
sample sd 7.51701e-16 C at n = 16; term 1's has mean 5.58122 % and sample sd
3.83503 % at n = 100 (SE of the mean 0.383503 %). Both are the campaign's own
committed statistics, quoted in the record's per-corner breakdown.

Two derived constants follow from the table, and every figure in §Decision is
one of them times a percentage:

- **The total the ratified line allows.** Running `spec/pll.md`'s own chain
  backwards from ≤ −55 dBc at 200 MHz: `θ = 2·10^(−55/20) = 3.556559e-3 rad`,
  `TIE = θ/(2π·200 MHz) = 2.83022 ps`, `V = 1.825 mV × 2.83022/0.669 =
  7.72070 mV`, `ΔQ = V·C2 = ` **14.00536 fC**. Unchanged by this record — it
  is a function of the ratified line and DR-006's C2, neither of which moves.
- **The term-1 charge per unit mismatch fraction.**
  `Icp × T_ov = 7.20923 µA × 2.58390 ns = ` **18.62794 fC**, so a term-1
  figure of `m` costs `m × 18.62794 fC`. Unchanged: both factors are
  `cp-compliance`/`pfd-deadzone` figures over the full 45-corner grid and
  neither campaign was re-run.

### The stack, before and after

The two non-term-1 terms add linearly (two different corners' worst cases, as
DR-018 stacked them):

- **was** 3.67840 + 4.25246 = 7.93086 fC → `spec/pll.md` wrote **7.93 fC**
- **now** 3.67840 + 5.56626 = **9.24466 fC** → **9.24 fC**

and the leftover for term 1 is `14.00536 − 9.24466 =` **4.76070 fC**, against
DR-018's 6.07450 fC. Carrying each total through the same
`ΔQ/C2 → TIE → θ = 2π·f_out·TIE → 20·log₁₀(θ/2)` chain, unrounded:

| Row of `spec/pll.md`'s charge-accounting table | Total ΔQ (was → now) | Derived spur (was → now) | Margin to −55 dBc |
|---|---|---|---|
| Systematic asymmetry alone (no statistical term) | 3.68 fC → **unchanged** | −66.6 dBc → **unchanged** | 11.6 dB |
| Systematic + nominal-only statistical residual (the historical −61 dBc row) | 6.67 fC → **unchanged** | −61 dBc → **unchanged** | 6.0 dB |
| Corner-combined statistical residual, term 1 still excluded | 7.93 → **9.24 fC** | −59.9 → **−58.6 dBc** (−58.608) | 3.61 dB |
| …plus term 1 at its **measured** signed \|mean\|+3σ | 11.19 → **12.43 fC** | ≈ −57.0 → **−56.0 dBc** (−56.038) | 1.04 dB |
| …plus term 1 at its **budgeted** ±20 % | 11.66 → **12.97 fC** | −56.6 → **−55.7 dBc** (−55.667) | **0.67 dB** |

Arithmetic for the two term-1 rows: `0.170863 × 18.62794 = 3.18282 fC`, and
`9.24466 + 3.18282 = 12.42748 fC`; `0.20 × 18.62794 = 3.72559 fC`, and
`9.24466 + 3.72559 = 12.97025 fC`. The first two rows do not move because
neither prices term 3 from this campaign: the −66.6 dBc row is the systematic
asymmetry alone (the row DR-024 Decision 4 says a mismatch-off measurement is
comparable with) and the −61 dBc row is the *nominal-only* 2.99 fC residual,
retained as the historical cross-check it always was.

**Term 1's "measured" figure moves too, and that is a consequence of citing
one record rather than a second decision.** The table's measured row and its
term-3 row have to come from the same campaign run, or the column is a mix of
two corner axes; the widened axis' own signed worst corner is 17.0863 %
(`sf`/−40 °C/3.63 V) where the superseded axis read 17.4798 %
(`ff`/−40 °C/3.63 V). It *fell*, by 0.39 points — worth −0.073 fC, against
term 3's +1.31 fC — and most of the fall is the execution host, not the axis
(the record's re-grading table: −0.5525 pt host, +0.1590 pt axis). Nothing
about term 1's budget, its statistic or its verdict changes here.

### The ceiling the spur line puts on term 1, re-derived

`m_ceiling = 4.76070 fC / 18.62794 fC = ` **25.557 %**, against DR-018's
32.610 %. The 5 %-granular ladder DR-018 chose from, recomputed at the new
term 3 (each row `9.24466 fC + m × 18.62794 fC`, carried through the same
chain):

| Term-1 figure | ΔQ₁ | Total ΔQ | Derived spur at 200 MHz | Margin to −55 dBc |
|---|---|---|---|---|
| 4.7 % (systematic worst, what DR-006 §8 priced) | 0.875 fC | 10.120 fC | −57.82 dBc | 2.82 dB |
| 10 % | 1.863 fC | 11.107 fC | −57.01 dBc | 2.01 dB |
| 15 % | 2.794 fC | 12.039 fC | −56.31 dBc | 1.31 dB |
| **17.0863 % (measured, n = 100/corner, 21 corners)** | 3.183 fC | 12.427 fC | **−56.04 dBc** | **1.04 dB** |
| **20 % (DR-018's budget, retained)** | 3.726 fC | 12.970 fC | **−55.67 dBc** | **0.67 dB** |
| 25 % | 4.657 fC | 13.902 fC | −55.07 dBc | 0.07 dB |
| 25.557 % | 4.761 fC | 14.005 fC | −55.00 dBc | **0** |
| 30 % | 5.588 fC | 14.833 fC | −54.50 dBc | **−0.50 dB (fails)** |

### The corner-consistent reading, which is the part that is *not* alarming

The stack above is deliberately over-conservative in five separate ways at
once: three different corners' worst cases added linearly, the worst-corner
`Icp` and the worst-corner `T_ov` taken from two further corners, and term 1
counted *on top of* term 3 even though term 3's bench is the full `pfd_cp`
hierarchy with mismatch on and therefore already contains it. Read
corner-consistently instead — each of the 21 measured corners with **its own**
term 1, term 3, systematic asymmetry, `Icp` at code 11 and `T_ov` — the worst
corner is:

| Corner | q_systematic | term 3 | ΔQ₁ = m·Icp·T_ov | Total | Derived spur |
|---|---|---|---|---|---|
| `ff`/125 °C/3.63 V (worst) | 3.37510 fC | 5.49370 fC | 1.10442 fC (m = 10.1325 %, Icp 7.20923 µA, T_ov 1.51193 ns) | **9.97323 fC** | **−57.95 dBc** |
| `sf`/125 °C/3.63 V (term 3's own worst corner) | 3.19440 fC | 5.56626 fC | 1.14378 fC (m = 8.6694 %, Icp 7.16373 µA, T_ov 1.84168 ns) | 9.90444 fC | −58.01 dBc |
| `ff`/−40 °C/2.97 V (best) | 1.61160 fC | 1.58721 fC | 1.43660 fC (m = 16.6847 %, Icp 6.76610 µA, T_ov 1.27256 ns) | 4.63541 fC | −64.60 dBc |

So the worst *single corner* of the 21, taken self-consistently, sits **2.95 dB
inside** the ratified line, and term 1's corner-consistent contribution spans
1.104 fC (`ff`/125 °C/3.63 V) to 2.080 fC (`ss`/−40 °C/2.97 V) — against
3.183 fC stacked. The corners anti-correlate, exactly as DR-018 observed at the
3-point axis: term 1's binding corner is cold and term 3's is hot, and the
longest `T_ov` is at a third corner again. **This record does not adopt the
corner-consistent reading as the spec's convention** — changing which
convention a ratified derivation uses is a bigger decision than re-pricing one
of its inputs, and it would be choosing a convention because it passes. It is
reported because a 0.67 dB stacked margin read without it invites the wrong
conclusion.

## Decision

**1. Term 3 in the reference-spur charge stack is priced at 5.56626 fC**, the
worst corner (`sf`/125 °C/3.63 V) of the 21-point axis in
`sim/mc-cp-mismatch/records/20260927-102154-d004d5b.md`, replacing the
4.25246 fC DR-018 took from the superseded 3-point axis. `spec/pll.md`'s
charge-accounting table cites that record by id, so
`spec/lib/check-mismatch-charge-derivation.sh` re-derives the figure and every
total built on it from its committed CSVs.

**2. `spec/pll.md`'s three DR-018-era derived rows move, and the ratified row
does not.** 7.93 → 9.24 fC (−59.9 → −58.6 dBc), 11.19 → 12.43 fC (≈ −57.0 →
−56.0 dBc), 11.66 → 12.97 fC (−56.6 → −55.7 dBc). The
[Reference spur](../pll.md#reference-spur) **target stays ≤ −55 dBc** and the
fully stacked bound still clears it, by **0.67 dB**. The summary table's row 7
carries −55.7 dBc where it carried −56.6 dBc, because that is the figure the
row's margin claim is stated from. No other ratified row moves, and no
verdict in `design/README.md`'s mismatch table moves.

**3. Term 1's budget stays ±20 %, and DR-018's selection rule is retired
rather than met.** The rule DR-018 §Decision 2 chose 20 % by — "the largest
5 %-granular value that keeps the conservatively stacked derivation at least
1.5 dB inside the ratified −55 dBc" — is **not satisfiable at the widened
axis**, and the arithmetic says so without ambiguity. 1.5 dB inside −55 dBc
is a total of `14.00536 × 10^(−1.5/20) = 11.78404 fC`, which leaves
`11.78404 − 9.24466 = 2.53938 fC` for term 1, i.e. **13.632 %**. The largest
5 %-granular value under that is **10 %** — below the measured 17.0863 %. So
the rule now admits only budgets the block is already measured to breach.
(At the 3-point axis the same rule admitted 20.685 %, which is why 20 % was
its answer then; the rule did not change, its input did.)

±20 % is therefore retained on a **narrower, stated basis**, and this is the
weakening this record is honest about:

- the measurement fits it — 17.0863 % is **85.4 %** of ±20 % at the widened
  axis (DR-018 recorded 87.4 % at the superseded one), with the budget line
  7.598 standard errors of the binding corner's mean above the statistic;
- the fully stacked bound at ±20 % still **clears the ratified line**
  (−55.67 dBc), which is the only hard requirement;
- the corner-consistent bound at ±20 % clears it with room — replacing each
  corner's measured term 1 by the budget, the worst of the 21 corners is
  `sf`/125 °C/3.63 V at
  `3.19440 + 5.56626 + 0.20 × 7.16373 µA × 1.84168 ns × 1e15 = 11.39932 fC`
  → **−56.79 dBc**, **1.79 dB** inside the line (at the *measured* per-corner
  term 1 the worst corner is `ff`/125 °C/3.63 V at −57.95 dBc, 2.95 dB
  inside);
- and narrowing the budget is not available: any value that restores 1.5 dB of
  stacked margin is below the measurement, so it would record a charge-pump
  failure that the corner-consistent evidence does not support, against a term
  no available mechanism can move (DR-018 §Alternatives measured both levers
  dead — the `Icp` trim has no differential authority over term 1, and the PFD
  reset overlap is fixed at 24 stages by `sim/pfd-deadzone`).

**4. The forward rule that replaces DR-018 §Decision 2's — its own 1.5 dB
criterion, moved onto the reading that can still carry it.** DR-018's rule was
"≥ 1.5 dB inside −55 dBc, 5 %-granular, on the stacked derivation". The
criterion is kept; the reading it is applied to changes, because the stacked
one has stopped discriminating (every value from 5 % to 20 % now sits inside
1.5 dB of the line, so the rule can only reject, never choose). A term-1
budget is now graded on **two** conditions:

- (a) the **stacked** bound at that budget must clear the ratified −55 dBc at
  all — 5 %-granular still, and this is a floor, not a margin; and
- (b) the **corner-consistent** bound at that budget — each of the measured
  corners with its own term 3, systematic asymmetry, `Icp` at code 11 and
  `T_ov` — must sit at least **1.5 dB** inside −55 dBc at every one of them.

**Applied to today's evidence this rule returns ±20 %, the same answer
DR-018's did**, which is the reason it is the replacement rather than an
invention: the corner-consistent worst corner (`sf`/125 °C/3.63 V throughout)
reads −57.31 dBc at 15 % (2.31 dB), **−56.79 dBc at 20 % (1.79 dB)** and
−56.30 dBc at 25 % (1.30 dB), so 20 % is the largest 5 %-granular value
satisfying (b), and (a) holds there with 0.67 dB. A widening of term 1's
budget is **not** an available response to either condition failing: at
25.557 % the stacked bound reaches the line exactly, and that ceiling is not
spare budget.

**5. §Decision 5's fail-loud condition, restated at the new figures.** Say so
in a **new** decision record — not by widening a budget — if any of the
following is measured:

- term 1 above **20 %** under either the signed or the folded reading
  (unchanged from DR-018);
- term 3 above **the leftover the line allows once term 1 is at its budget**,
  i.e. `14.00536 − 3.72559 − 3.67840 =` **6.60137 fC** at the systematic
  asymmetry's present worst case — the point at which the stacked bound stops
  clearing −55 dBc with term 1 at ±20 %. The 21-point axis reads 5.56626 fC,
  which is **84.3 %** of that. This condition is new: DR-018 had no term-3
  trip point because term 3 was not the term that had moved;
- the corner-consistent product at any corner exceeding **4.76070 fC** for
  term 1 alone (DR-018's 6.07450 fC, re-derived), or any corner's
  corner-consistent **total** exceeding 11.78404 fC (condition 4(b));
- the systematic asymmetry above 3.67840 fC, which enters the same sum and has
  no allowance of its own here.

**6. Nothing is re-measured and nothing in `design/` changes.** This record is
arithmetic on committed evidence: no simulation was run for it, no `sim/`
record was edited, no netlist, sizing or trim code moves, and the campaign
record that found the exceedance keeps its bytes and its PASS verdicts.

## Alternatives considered

- **Narrow term 1's budget until DR-018's 1.5 dB rule is satisfied again.**
  The first candidate, because it keeps the rule rather than the number.
  **Arithmetically dead**: the rule admits at most 13.632 % and the largest
  5 %-granular value under that is 10 %, both below the measured 17.0863 %. A
  budget set there converts a measurement that PASSes into a FAIL by
  redefinition, against a term DR-018 already measured to have no available
  correction mechanism. CLAUDE.md forbids relaxing a spec to make results
  pass; it equally forbids tightening a *design budget* into a failure to
  preserve the tidiness of a selection rule whose premise — that the stack had
  1.5 dB to give — the measurement has falsified.
- **Keep `spec/pll.md` citing the superseded 3-point record and leave the
  stack at 4.25246 fC.** The lowest-churn option, and the one with the worst
  property: the specification would state a derivation whose worst-corner
  input is known to be superseded, and `check-mismatch-charge-derivation.sh`
  would go on re-deriving 4.25246 fC and reporting green. `sim/`'s
  append-only rule protects the *record's bytes*, not the spec's right to
  keep citing an input a later campaign has bettered — the successor record
  says so itself ("what this record owes is the measurement and the flag").
- **Re-price term 3 but hold term 1's "measured" row at 17.4798 %.** Tempting
  because term 1 fell and holding the higher figure looks conservative. It
  mixes two corner axes in one column of one table, and it breaks the
  single-record citation both CI checks resolve the table's ingredients
  through. The conservatism it buys is +0.073 fC, or 0.05 dB — bought by
  making the table unauditable. Rejected. The figure is quoted in §Context so
  the difference is visible without it.
- **Use term 3's pooled all-corner statistic (6.00349 fC) instead of the worst
  corner's.** Larger, so "more conservative", and superficially attractive for
  a bound. Rejected on the campaign's own methodology: the record states that
  pooling across corners mixes the systematic corner-to-corner spread into
  what is supposed to be a within-corner mismatch σ, and it reports the pooled
  figure explicitly as *not* the verdict statistic. Every other term in this
  stack is a per-corner worst case; mixing one pooled figure in would make the
  sum an inconsistent object, not a more careful one.
- **Adopt the corner-consistent reading as the derivation's convention**
  (worst single corner, −57.95 dBc, 2.95 dB inside). The most physically
  defensible number in this record, and still rejected: changing which
  convention a ratified derivation is stated in is a larger decision than
  re-pricing one of its inputs, it would be adopted in the same commit that
  the stacked reading became uncomfortable, and the stacked reading's own
  virtue — that it cannot be beaten by an unvisited corner combination — is
  exactly what a 24-point-short grid still needs. It is reported as the
  cross-check (§Context) and as condition 4(b), which is where it does work
  without silently buying margin.
- **Widen the ratified spur line, or restate it at a lower output frequency
  where the bound improves.** Forbidden outright: agents do not relax the
  ratified spec to make results pass, and 200 MHz is the binding frequency of
  the ratified band.
- **File this as an amendment to DR-018 rather than a new record.** The route
  Amendment A1 took, and correctly so there: A1's change was *pre-authorised*
  by DR-018 §Decision 3 and moved no decision. This one is not. It retires a
  selection rule DR-018 stated, changes a ratified derivation's input, and adds
  a new fail-loud trip point — three decisions DR-018 does not contain. Per its
  own A1 ("If a future change moves a ratified value, or goes past what
  §Decision 3 authorised, it needs a new record"), this is a new record.
- **Re-run the campaign at the full 45 points first.** Rejected on the issue's
  own terms and on arithmetic: the 24 unvisited points are interior on the
  temperature and supply axes at bundles whose ends are both measured, the
  measurement in hand already moved the figure, and a larger grid can only move
  term 3 further up — it cannot restore the 1.5 dB. The remaining grid is
  tracked by the campaign, not blocked on this record.

## Consequences

- **`spec/pll.md`'s charge-accounting table carries 9.24 / 12.43 / 12.97 fC
  and −58.6 / −56.0 / −55.7 dBc**, cites
  `run.sh --restat 20260927-102154-d004d5b`, and names this record as term 3's
  pricing authority. Its summary-table row 7 carries −55.7 dBc.
  `check-mismatch-charge-derivation.sh` re-derives all three totals from the
  five ingredient campaigns, and `check-spur-derivation-arithmetic.sh`
  re-derives each row's dBc from its own ΔQ.
- **The derived spur's margin against the ratified line falls from 1.6 dB to
  0.67 dB, and that is the bad consequence of this record, stated rather than
  buried.** The reference-spur row now has three uncomfortable facts in one
  section of the spec: a stacked derivation 0.67 dB inside the line, a measured
  150 MHz campaign whose two cold corners are 0.5 and 0.1 dB *outside* it once
  scaled to 200 MHz, and zero measured points at the binding 200 MHz
  (`sim/reference-spur-band-top`, owed at #533). None of them is repaired here.
- **The stack's conservatism is now load-bearing rather than decorative.**
  At 1.6 dB it was reasonable to read the stacked row as the number; at
  0.67 dB the gap between it and the corner-consistent −56.79 dBc at the same
  ±20 % is more than the remaining margin. Anyone quoting this row must say
  which reading they mean, which is why §Decision 4 grades both.
- **A term-1 widening is no longer available as a response to anything.** The
  ceiling is 25.557 %, ±20 % sits 1.28× under it (DR-018: 1.63×), and
  §Decision 4 names the corner-consistent condition a future record is graded
  on instead. `sim/mc-cp-mismatch/testbench/run.sh`'s `TERM1_BUDGET_PCT=20`
  does not change.
- **`design/README.md`'s mismatch-budget section is refreshed**: the ceiling
  bullet (14.005 fC allowed, 3.68 + 5.56626 = 9.24 fC taken, 4.76 fC left,
  25.6 % ceiling), the ±20 %-rationale bullet (1.28× under the ceiling, 85.4 %
  utilisation), and the widened-axis bullet's "owed beyond this table" flag,
  which this record closes. **No budget column moves and no verdict moves.**
- **`sim/CHARACTERIZATION.md`'s `mc-cp-mismatch` row and
  `docs/chipalooza/challenge-5-proposal.md`'s Reference spur row both had this
  re-pricing declared as owed; both now state the verdict.** The proposal's
  derived-figure table and its §5.1 provenance entry for term 1 move to this
  record's figures and to the 21-point record id.
- **One CI check changed shape, and it is the sibling of the change above.**
  `check-mismatch-charge-derivation.sh` used to grade term 3's reduction
  against **DR-018's** Input row while reducing it from whichever record
  `spec/pll.md` cites — a cross-grading that fails the moment the spec's
  citation moves forward, for the right reason and in the wrong place. It now
  reads the pricing decision record out of `spec/pll.md` itself ("priced by
  DR-NNN at X fC"), grades X against the reduction, and requires that record's
  own Input row to state the same figure **and** cite the same record id. So
  DR-018 keeps its 4.25246 fC as a true statement about the evidence it cited,
  this record's 5.56626 fC is the graded one, and the next re-pricing changes
  one sentence in the spec instead of needing a check edit.
- **Nothing is invalidated in `sim/`.** The superseded 3-point record keeps its
  bytes and its per-corner numbers; DR-018's arithmetic remains correct for the
  evidence it cited; the 4.25246 fC figure stays readable in both places as
  what the narrower axis could see.
- **The path to needing this record again is narrow and named**: a term-3
  measurement above 6.60137 fC (24 interior grid points remain unvisited, and
  the bias generator is still excluded from this campaign entirely), any
  corner-consistent total above 11.78404 fC, or a closed-loop spur measurement
  at the binding 200 MHz that does not clear −55 dBc. The third is a spec-row
  problem no charge-pump budget can fix, and it is owed at #533.
