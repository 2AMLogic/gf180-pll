# DR-018: Charge-pump term 1's up/down mismatch budget is widened ±12 % → **±20 %**, and is re-derived from the ratified reference-spur line instead of from headroom over the systematic measurement

- **Status**: proposed, drafting for operator ratification via PR review — the
  same `2AMLogic/2am#357` ratification-via-PR route DR-007, DR-009 … DR-017
  record (a builder drafts the record on the evidence; the operator's PR
  approval is the ratifying act). Status stays `proposed` until that approval
  and merge. `design/README.md`'s budget table is *downstream* of this decision
  and cites it as binding in the same commit; that is the same position DR-016
  was in when it amended a ratified `spec/pll.md` row inside its own filing
  commit, and it left this field `proposed` — the downstream prose is
  declarative about the *decision*, not about this field, and reads correctly
  either way. Whether a record in that position should instead be filed
  `ratified` is the governance question #446 refers to the operator; this
  record does not pre-empt it, and #483's acceptance criterion asking for
  `ratified` is relaxed on that basis (see the note on #483).
- **Date**: 2026-09-23
- **Decided by**: Builder agent, issue #483 (successor to the measurement in
  PR #484 / issue #482)
- **Relationship to DR-006**: **refinement, not supersession.** DR-006 stays
  `ratified` and binding; its Decision 1 (C2 sizing) and Decision 5 (the Icp
  trim-code rule) are unchanged and this record re-states neither. What this
  record touches is one parenthetical in DR-006 §8 — "the UP/DN *current*
  mismatch during the ~1 ns anti-backlash window contributes under 1 fC" —
  which is true of the *systematic* term and not of the statistical 3σ tail
  (§Consequences). No `superseded by` pointer is owed and none is added.

## Context

`design/README.md`'s "Up/down mismatch budget" table allocates **±12 %** to
term 1, the DC UP/DN current mismatch `(Iup − Idn)/Iavg` taken at the worst
point of the 0.9–2.4 V compliance window. That figure was never derived from a
spec quantity. The table's own note says what it was: a number set "well above
the measured systematic value" (−2.7 … +4.7 % across 45 corners) to leave room
for the random device mismatch the systematic measurement excludes.

#15's Monte Carlo campaign, re-run corner-combined at n = 100 samples/corner
(`sim/mc-cp-mismatch/records/20260923-095854-1655e11.md`, issue #482), measures
that term at **13.2172 %** at `ff`/−40 °C/3.63 V — outside the ±12 %. It is not
a marginal call: sample sd 2.76942 %, standard error of the mean 0.276942 %, so
the budget line sits **4.4 standard errors** below the statistic. The
superseded n = 20/corner record's 11.7211 % PASS had a 2.3 % relative margin
that was smaller than its own sampling uncertainty. Nothing about the design
changed between the two records; only `N_DC` did.

`design/README.md` states the rule for exactly this case — "the resolution is a
decision record superseding this budget, not a quiet relaxation here" — and the
campaign that found the exceedance left the budget column untouched and routed
the resolution to #483. This is that record.

### What term 1 actually buys, in the ratified spec

Term 1 is an intermediate quantity. It reaches a ratified spec row through
exactly one path: the PFD's reset overlap turns an UP/DN *current* mismatch
into a once-per-reference-cycle charge on the loop filter, and that charge is
the [Reference spur](../pll.md#reference-spur) mechanism (target **≤ −55 dBc**,
ratified). With `m` the mismatch fraction and `T_ov` the reset overlap:

- static phase offset `Δt = m · T_ov` (the "overlap × mismatch fraction"
  formula `design/README.md` already carries), and
- ripple charge on C2 `ΔQ₁ = Icp · Δt = m · Icp · T_ov`.

Both are **measured, not assumed**:

| Input | Value | Source |
|---|---|---|
| Reset overlap `T_ov`, min UP/DN pulse at zero phase error, 45 corners | 1.113 – 2.584 ns (worst `ss`/125 °C/2.97 V) | `sim/pfd-deadzone/corners/20260916-051356-8cedbba/raw_measures.csv` |
| `Icp`, largest trim code (11, four unit legs), 45 corners | 6.71 – 7.21 µA | `sim/cp-compliance/records/20260801-190821-734f483.md` |
| Systematic per-event charge asymmetry \|q_up + q_dn\| | 3.68 fC worst corner | `sim/cp-compliance/…-061841-c24ee3a` via DR-006 §8 |
| Statistical residual net charge (term 3), corner-combined \|mean\|+3σ | 4.25246 fC | `sim/mc-cp-mismatch/…-095854-1655e11` |
| C2, worst-case minimum over corners | 1.814 pF | DR-006 Decision 1 |
| TIE per unit ripple | 0.669 ps at 1.825 mV | DR-006 §8 / `sim/loop-dynamics` §7 |

Code 11 is reachable at the binding f_out = 200 MHz (N = 64, f_ref =
3.125 MHz, which the [Icp trim-code rule](../pll.md#icp-trim-code-rule) maps to
four unit legs), so it is the bounding code, not a hypothetical one.

### The ceiling the spur line puts on term 1

Running `spec/pll.md`'s own narrowband-FM chain backwards from the ratified
−55 dBc at 200 MHz — `θ = 2·10^(−55/20)`, `TIE = θ/(2π f_out)`,
`V = 1.825 mV · TIE/0.669 ps`, `ΔQ = V·C2` — the total per-cycle charge the
target permits is **14.005 fC**. The two terms that are not term 1 consume
3.68 + 4.25246 = **7.933 fC** (linear add of two different corners' worst
cases), leaving **6.073 fC**. At the bounding `Icp` = 7.21 µA and `T_ov` =
2.584 ns that is:

> **m_ceiling = 6.073 fC / (7.21 µA × 2.584 ns) = 32.6 %**

and the derived spur as a function of the term-1 budget, under that same
deliberately conservative stacking (worst `Icp` and worst `T_ov` from different
corners than the charge terms, and term 1 counted *on top of* term 3 even
though term 3's own bench already contains it):

| Term-1 figure | ΔQ₁ | Total ΔQ | Derived spur at 200 MHz | Margin to −55 dBc |
|---|---|---|---|---|
| 4.7 % (systematic worst, what DR-006 §8 priced) | 0.876 fC | 8.808 fC | −59.03 dBc | 4.03 dB |
| 12 % (the outgoing budget) | 2.236 fC | 10.168 fC | −57.78 dBc | 2.78 dB |
| **13.2172 % (measured, n = 100)** | 2.462 fC | 10.395 fC | **−57.59 dBc** | **2.59 dB** |
| 17.48 % (the stricter signed reading, below) | 3.257 fC | 11.189 fC | −56.95 dBc | 1.95 dB |
| **20 % (this record)** | 3.726 fC | 11.659 fC | **−56.59 dBc** | **1.59 dB** |
| 25 % | 4.658 fC | 12.590 fC | −55.93 dBc | 0.93 dB |
| 32.6 % | 6.073 fC | 14.005 fC | −55.00 dBc | **0** |

Read corner-consistently instead of stacked — each corner's own mismatch
statistic, its own `Icp` at code 11 and its own `T_ov` — the measured term 1
costs 1.02 fC at `ff`/−40 °C/3.63 V, 1.08 fC at `typical`, and 1.53 fC at
`ss`/125 °C/2.97 V (the corners anti-correlate: the largest mismatch sits at
the corner with the *shortest* overlap). The stacked 2.46 fC row above is
therefore a bound, not a per-die figure.

### The statistic, checked rather than assumed

`sim/mc-cp-mismatch/testbench/run.sh` forms term 1 as `mean(|x|) + 3·sd(|x|)`
over the per-sample worst-of-three-Vctrl-points **magnitude**. Re-deriving it
from the committed 300 raw samples reproduces 13.2171 % exactly, and shows the
folding is what makes it small: on the *signed* samples at the binding corner
the systematic mean is +2.86 % and the mismatch σ is 4.87 %, so a literal
reading of the table's own column header ("Budget (3σ, incl. random mismatch)")
gives **17.48 %** (worst-of-three convention kept) or **16.28 %** (single worst
Vctrl point, 0.9 V). The convention in force is not conservative — it is
**1.3× optimistic** against a plain 3σ. That kills the third candidate
resolution before it starts (§Alternatives) and it sets the bar this record's
number has to clear.

## Decision

**1. Term 1's budget is ±20 %**, replacing ±12 % in `design/README.md`'s
"Up/down mismatch budget" table. `spec/pll.md`'s [Reference
spur](../pll.md#reference-spur) row — ≤ −55 dBc — **does not move**, and no
other ratified row moves either. The budget is a design-side allocation under
the spur line, not a spec line, exactly as the table already says.

**2. ±20 % is chosen by a stated rule, not by what the measurement needs**: it
is the largest 5 %-granular value that keeps the conservatively stacked
derivation of §Context at least **1.5 dB inside** the ratified −55 dBc (20 % →
1.59 dB; 25 % → 0.93 dB, rejected). It lands at:

- **1.63×** below the 32.6 % ceiling the spur line puts on this term;
- **1.51×** above the measured 13.2172 % (66 % budget utilisation, against
  110 % under the outgoing ±12 %);
- **1.14×** above the stricter signed 17.48 % reading, i.e. the budget holds
  under *both* readings of the statistic — which is the reason it is not set at
  15 %, a value that would fit the measurement and fail the column header.

**3. The statistic the budget is checked against is named, so it cannot drift.**
Term 1's verdict is `mean(|x|) + 3·sd(|x|)` on the per-sample worst-magnitude
across the Vctrl window, at the **worst corner** (not pooled), as
`sim/mc-cp-mismatch/testbench/run.sh` computes it. A future campaign that
reports the signed `|mean| + 3σ` form instead — which would be the more honest
statistic, and is filed as #487 — checks **the same ±20 %**, without a
further record: both readings were priced above.

**4. What ±20 % does not cover, stated so it cannot be absorbed silently.**

- **The bias generator.** Its mirror mismatch is excluded from this campaign
  (`IBN`/`ICN`/`IBP`/`ICP` are driven from ideal sources) and is *not*
  pre-allocated here. `design/README.md`'s existing rule stands: when that
  block lands, the budget is re-derived, not stretched.
- **The 42 unvisited PVT points.** The campaign runs a 3-corner subset; `fs`,
  `sf` and the off-diagonal crossings are unmeasured. The margin between
  13.22 % and 20 % is where they have to fit, which is a second reason the
  budget is not set at 15 %.
- **The reference-spur row's own open gap.** The measured closed-loop spur
  (`sim/reference-spur/…-132150-5f405e7`, mismatch **off**) is −57.0 dBc worst
  at 150 MHz, i.e. −54.5 dBc scaled to 200 MHz — already 0.5 dB outside the
  target at two cold corners, as `spec/pll.md`'s Verification-owed table says.
  **This record does not repair that and must not be read as doing so.** What
  it does establish is that term 1 is not what decides it: at the operating
  point that measurement was actually taken (f_ref = 25 MHz, trim code 00), the
  whole ±12 % → ±20 % widening is worth **0.37 fC** — an order below the
  −1.60 … +2.78 fC settling drift that record reports as its own per-point
  uncertainty, and below the 2.16 – 3.68 fC asymmetry the spur is made of.

**5. Fail-loud condition.** If a future record measures term 1 above **20 %**
under either reading, or if the corner-consistent `m · Icp · T_ov` product at
any corner exceeds the **6.07 fC** allocation above, say so in a new decision
record rather than widening this one again. The 32.6 % ceiling is not spare
budget — it is the point at which the ratified spur line fails outright, with
every other term already at its worst case.

## Alternatives considered

- **Tighten the design with the existing 2-bit `Icp` trim.** The candidate
  `design/README.md` itself names ("term 1 is what the 2-bit trim exists for"),
  and the first one to check because it needs no spec change at all.
  **Measured dead, twice over.** (a) *Structurally*: the committed netlist
  (`.subckt cp UP DN B0 B1 …`) gates four N legs and four P legs off **one**
  `B0`/`B1` pair — `xn_base`/`xn_t0`/`xn_t1a`/`xn_t1b` against
  `xp_base`/`xp_t0`/`xp_t1a`/`xp_t1b` — so a code change moves `Iup` and `Idn`
  by the same factor and leaves their *ratio* alone. The trim sets loop
  bandwidth; it has no differential authority. (b) *Numerically*: across all
  45 PVT corners, stepping the code from 00 to 11 (a 4× current change) moves
  term 1's worst-in-window mismatch by at most **0.066 percentage points**
  (median 0.015 pp) — `sim/cp-compliance/corners/20260801-190821-734f483/cp_dc.csv`.
  That is the trim's entire authority over term 1, against a 13.2 % tail: short
  by more than two orders of magnitude. Even a hypothetical per-polarity split
  code would quantise at one unit leg — 100 %/50 %/33 %/25 % of `Icp` for codes
  00/01/10/11 — so its finest step is ~2× the tail it would be correcting, and
  its quantisation residue (±12.5 % at best) is no better than the ±12 % line
  it was meant to rescue. Choosing this path would have meant claiming a
  correction mechanism that the schematic does not implement.
- **Ratify a different statistic.** Attractive on its face: the worst-of-three
  convention takes a max over three correlated points before forming a tail.
  **Rejected because the honest version of it moves the number the wrong way.**
  The statistic in force folds the distribution before taking `mean + 3·sd`,
  and folding *shrinks* the result: the same 300 samples give 13.22 % folded
  and 17.48 % signed. Anything defensible as "a proper 3σ" therefore makes the
  exceedance larger, not smaller. Adopting a *looser* statistic — pooling
  corners (10.94 %), or quoting the 99th percentile (12.71 %) — would be
  choosing a statistic because it passes, which is the one thing #483 and
  CLAUDE.md both forbid. The convention's optimism is real and is filed as
  **#487**; it is not this record's lever.
- **Hold ±12 % and declare the block non-compliant.** The correct action *if*
  there were a lever to pull, and there is not: the trim cannot move term 1
  (above), and the only other lever — shortening the PFD reset overlap — is
  fixed at 24 inverter stages by the charge-pump turn-on measurement
  (`sim/pfd-deadzone`; a 6-stage chain flattened the phase-to-charge transfer
  at 9 of 45 corners). Holding a budget that no available mechanism can move,
  against a spur line whose derivation clears −55 dBc by 2.6 dB *at the
  measured mismatch*, records a charge-pump failure that does not exist. (The
  spur row's own 200 MHz-extrapolation gap is real and is separately tracked;
  it is not a term-1 problem, per Decision 4.)
- **Widen to the 32.6 % ceiling** (or to ~30 %, "the derivation's own limit
  with a token round-down"). Rejected: the ceiling is where the ratified spur
  target fails with every other term simultaneously at its worst case, so a
  budget set there has zero allowance for the 42 unvisited corners, for the
  bias generator, or for layout coupling that does not exist yet. A budget must
  be somewhere a violation still means something.
- **Widen to exactly 13.5 %, the measurement plus a sliver.** Rejected on two
  counts: it fails the column header (the signed 3σ reading is 17.48 %), and it
  would be re-breached by the first `fs`/`sf` corner the campaign has not yet
  visited — an upward re-amendment of a fresh record, the direction CLAUDE.md
  most disfavours.
- **Re-run the campaign at n = 200 first.** Rejected on the issue's own terms
  and on arithmetic: the statistic is 4.4 standard errors past the line, so a
  larger sample sharpens the figure without changing its sign. The existing
  record is corner-combined, carries its raw logs and netlist snapshot, and
  reports its own sampling uncertainty. Nothing here is blocked on more
  simulation.

## Consequences

- **`design/README.md`'s budget table carries ±20 % for term 1**, its term-1
  note states the resolution and points here, and the "budget is not a spec
  line" bullet records that the rule was exercised *and closed* rather than
  merely invoked. Terms 2/2a, 3 and 4 are untouched.
- **`sim/mc-cp-mismatch/testbench/run.sh` now reads its term-1 budget from a
  single named constant** (`TERM1_BUDGET_PCT=20`, citing this record) instead
  of a `12` hardcoded in six places — the verdict, the standard-error margin,
  and four spots in the record template's prose. Without that, the next run of the
  campaign would emit a FAIL against a superseded budget and a record whose
  prose argues for a decision record that already exists. **No simulation is
  re-run in this record** — `sim/` is append-only, the committed n = 100 record
  keeps its FAIL verdict and its bytes, and the change only affects what a
  *future* run reports.
- **A future re-run of the same campaign, on the same design, will report
  PASS where the committed record reports FAIL.** That transition is a budget
  change, not a measurement change, and anyone comparing the two records must
  read it that way — which is why `run.sh`'s header comment now says so in
  place of its "nothing in this script widens the budget" note.
- **DR-006 §8's "current mismatch contributes under 1 fC" is refined, not
  overturned.** That figure is right for the systematic 4.7 % (0.88 fC at the
  bounding code). At the statistical 3σ tail it is 1.02 – 1.53 fC
  corner-consistent and 2.46 fC stacked. DR-006's actual *decision* — C2 is
  sized by phase margin, not by ripple — survives, because the spur that falls
  out of the as-built C2 (−56.6 dBc) is still inside the ratified line. What
  does not survive is the slack in that section's illustration: its "even at
  0.5 pF, a quarter of the as-built C2, worst-case ripple would be 7.4 mV"
  becomes 23.3 mV once the statistical terms are priced, and the ripple at the
  as-built 2.02 pF is 5.8 mV rather than 1.83 mV. C2 is still not the binding
  knob; it is no longer nowhere near binding.
- **`spec/pll.md`'s reference-spur derivation gets the refreshed accounting**,
  as a note under the existing table rather than an edit to it: the −61 dBc row
  used the nominal-only term 3 (2.99 fC) and excluded term 1 entirely, and with
  the corner-combined term 3 and term 1 at this budget the same chain gives
  **−56.6 dBc**. The ~6 dB the spec reserves for uncovered mechanisms is
  therefore ~1.6 dB once the covered ones are priced at their statistical 3σ.
  **That is the bad consequence of this record and it is stated, not buried**:
  the spur line's derived margin is thin, the measured 200 MHz extrapolation is
  already 0.5 dB out at two cold corners, and both facts now sit in the same
  section of the spec.
- **`spec/pll.md`'s summary-table row 7 carries the second figure** alongside
  the −61 dBc it already quoted, so a reader of the table alone is not left
  with the more optimistic of the two.
- **`sim/CHARACTERIZATION.md`'s `mc-cp-mismatch` row is refreshed** to the
  n = 100 record (it still pointed at the superseded n = 20 one and quoted
  "11.72 % against ±12 %"), and states that the exceedance was resolved by
  amending the budget rather than by the measurement moving.
- **The statistic's mislabelling is filed as #487**, not fixed here. Both
  readings are priced above, so no verdict depends on it today; the correction
  makes term 1's reported figure larger, which is why it is not urgent and also
  why it must not be forgotten.
- **The path to needing this record again is narrow and named**: the bias
  generator landing (#1-era scope, still absent), an `fs`/`sf` corner measuring
  above 20 %, or a spur measurement at 200 MHz that does not clear −55 dBc. The
  first two re-derive this budget; the third is a spec-row problem that a
  charge-pump budget cannot fix.
- **Nothing in `design/` changes.** No schematic, no netlist, no sizing, no
  trim code — this record is an allocation decision on a measured design, and
  the design is byte-identical before and after it.
