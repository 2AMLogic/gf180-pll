# DR-036: The band-selection rule's "reaches `f`" is evaluated over the measured 0.9 – 2.7 V control window

- **Status**: proposed. Ratification is by the operator through the two-key
  ratification script (both RATIFY-KEY reviews), not by editing this field.
- **Date**: 2026-10-02
- **Decided by**: Operator ruling on issue #542 (2026-10-02), drafted by a
  Builder agent

## Context

`spec/pll.md`'s band-selection rule said only "configure the lowest 3-bit band
code that reaches `f`" and did not name the control-voltage window over which a
band "reaches" `f`. The repository carries two: DR-001 Decision 2's *predicted*
0.9 – 2.4 V and DR-003 Decision 5's *measured* 0.9 – 2.7 V
(`f(Vctrl)` monotonic on all 504 measured curves). They select different codes
and the rule is not satisfiable under both
(`sim/supply-sensitivity/records/20260925-090649-4422f1d.md`; reproduce with
`python3 sim/supply-sensitivity/testbench/band_rule_audit.py --outdir /tmp/band-rule`):

- at `ff`/27 °C, f_out = 100 MHz the measured window selects **band 5**
  (Vctrl 2.595 V) and the predicted window selects **band 6**;
- under the predicted window the rule has **no answer** at 4 of the 15
  (bundle, temperature) cells at 100 MHz (`fs`/27, `sf`/27, `ss`/−40,
  `typical`/27); under the measured window it has an answer at all 15.

DR-025 (issue #511) restates `spec/pll.md` row 9's corner count (2 of 45 to
1 of 45 measured at a rule-compliant configuration, plus 1 owed) using the
measured window and states that this is not yet normative. Issue #542 tracked
the question; the operator ruled on 2026-10-02 that the measured window is
normative.

## Decision

1. **The band-selection rule is evaluated over DR-003 Decision 5's measured
   0.9 – 2.7 V control window.** A band code reaches `f` at a PVT point when
   that point's f(Vctrl) curve for the band brackets `f` at some Vctrl in
   0.9 – 2.7 V. The rule text in `spec/pll.md` is amended to say so.
2. DR-001 Decision 2's predicted 0.9 – 2.4 V is not a reading of the rule. It
   remains the historical prediction; this record does not alter it or any
   other ratified record.
3. **No measured number moves.** This selects which reading of a normative
   rule is authoritative; it does not change any characterization of the VCO.
   Existing `sim/` records are append-only and are not edited.
4. The per-campaign re-check below is part of this decision. Where a campaign's
   configuration disagrees with the rule it is recorded as a deviation, not
   silently corrected.

### Re-check of the campaigns that derive a band code

| Campaign | Window used | Agrees? |
|---|---|---|
| `sim/supply-sensitivity/testbench/run.sh` (`derive_op_points`) | 0.9 – 2.7 V (defaults `lo=0.90`, `hi=2.70`), since #511 | **Yes.** `band_rule_audit.py` reproduces the rule-selected band at all 15 cells; the only disagreement with the campaign's committed grid is the already-recorded `ff`/27 °C cell (band 6 run, band 5 selected). The campaign's acceptance gate `ACC_VCTRL_LO/HI` = 0.9/2.4 V is a separate "Vctrl stays in the usable window" pass/fail check, not a band derivation; it is unchanged and recorded here as a deviation from the 0.9 – 2.7 V window (it is the stricter gate; no recorded result is invalidated, and any change to it would move a verdict, so it is left to a campaign issue). |
| `sim/reference-spur-band-top/testbench/band_and_vstart_from_vco_record.py` | 0.9 – 2.7 V, stated in its docstring; the committed table is sampled over exactly that window | **Yes.** `--check` passes: all 45 `tb.json` points match; band 6 at 34 of 45, band 7 at 11 of 45. |
| `sim/period-jitter-band-top` | 0.9 – 2.7 V, stated in `select_band` | **Yes.** `--check` passes with the same 34 / 11 split. |
| `sim/pll-top-smoke` | 0.9 – 2.4 V (comments in `run.sh`; `ACC_VCTRL_LO/HI`) | **No, deviation recorded.** The campaign's single operating point is `typical`/27 °C/3.30 V at N·f_ref = 72 MHz, run at band 5, justified as "the lowest band that reaches 72 MHz inside 0.9 – 2.4 V". In `sim/vco-tuning-range/corners/20260731-175947-0a12e6c/kvco_by_point.csv` band 4 reaches 72.69 MHz at 2.70 V, so over 0.9 – 2.7 V the rule selects **band 4** (Vctrl about 2.68 V), not band 5. The existing records (`20260801-085349-0e5c22d`, `20260802-160926-8456ff3`) are a measurement of band 5 and stay valid as such; they are a smoke test of functional lock, not a rule-compliant operating point, and no spec row cites them as one. Neither the deck nor the records are changed. |

Related, not changed by this record: **#534** reads the same band map, same
rule and same measured window at 200 MHz (no single static code covers the
ratified box at four of five MOS bundles); its dispositions are unaffected.
**#525** is likewise unchanged in substance; this record only fixes the window
both read. **#540**'s run 1 (`ff`/27 °C at band 5) is the correct run under
this decision. DR-025's two references to #542 remain accurate: both say the
window was un-named and owned by #542, and this record is that resolution.
DR-025's reclassification and its row 9 restatement hold as written.

## Alternatives considered

- **Normative 0.9 – 2.4 V (DR-001 Decision 2's prediction)** — not chosen: the
  rule then has no answer at 4 of 15 cells at 100 MHz, a spec gap, and the
  window is a prediction that DR-003 Decision 5 measured to be conservative.
- **No window in the rule (evaluated over whatever a campaign declares)** — not
  chosen: a reader could not reproduce a band selection from the spec alone,
  and campaigns could silently disagree, as `sim/pll-top-smoke` already does.

## Consequences

- The rule is reproducible from `spec/pll.md` plus the committed VCO record.
- `sim/pll-top-smoke`'s band 5 is a recorded deviation from the rule (above).
  If a rule-compliant smoke point is wanted, a new run at band 4 is a new
  record, not an edit.
- `sim/supply-sensitivity`'s 0.9 – 2.4 V acceptance gate is a recorded
  deviation from the window the rule uses; it remains the stricter check.
- Operating at the top of a lower band (for example band 4 at about 2.68 V)
  leaves little headroom to the 2.7 V edge; that is a consequence of the rule
  as ruled, and is the kind of question #534 already tracks.
- Until ratified, `spec/pll.md`'s amended text is proposed.
