# DR-036: The Output band row is derated from 200 MHz to 166 MHz for a part that holds one static band code; 200 MHz stays a per-operating-point envelope

- **Status**: proposed. Ratification is the two-key process (2am#1056), run by
  the operator; this record's status is not flipped by the builder. The operator's disposition
  (issue #534, comment of 2026-10-02) is "derate the ceiling". `spec/pll.md`
  is edited in the same commit, marked as amended-by-DR-036-pending, the
  position DR-016, DR-018 and DR-034 were in when they filed `proposed`.
- **Date**: 2026-10-02
- **Decided by**: Builder agent, issue #534, on the operator's disposition

## Context

`spec/pll.md`'s [Output band](../pll.md#output-band) row (row 1 of the summary
table) was ratified as 10 – 200 MHz, continuous, at every PVT corner, and
substantiated the ceiling as an envelope: B7 reaches 247.8 MHz at the binding
`all-slow`/−40 °C/3.63 V corner. The band code is a static configuration input
(DR-001 Decision 2) and nothing on-chip re-selects it. Read together, a part
that must hold one frequency across its whole operating box needs one code that
reaches it at all 9 temperature × supply points of its bundle, and the
committed VCO record shows that for 200 MHz four of five MOS bundles have none
(issue #534).

## Decision

1. The Output band row promises, for a system that programs one static band
   code and holds it over the full −40 … 125 °C × 2.97 – 3.63 V box in any MOS
   bundle, a ceiling of **166 MHz** — not 200 MHz. This is a ceiling, not a
   continuous 10 – 166 MHz range: below it the static-code windows have gaps
   (Decision 4). 166 MHz is 166.261 MHz rounded down:
   the highest frequency at or below the 200 MHz line that one static code
   holds in every bundle (band 6, ceiling at `ff`/−40 °C/3.63 V, 166.3 MHz).
2. 10 – 200 MHz remains true only as the per-operating-point envelope (the
   band-selection rule finds a code at each of the 45 points) and is stated as
   such, not as a static-code promise. The measured floor (6.449 MHz) and
   ceiling (247.8 MHz) are unchanged.
3. "Held by one static code" is defined as: the band's committed f(Vctrl) curve
   brackets the frequency inside 0.9 – 2.7 V (DR-003 Decision 5) at every
   temperature × supply point of the bundle, i.e. the frequency lies in
   [max band floor, min band ceiling] over the 9 points. The cross-bundle
   figure intersects the five bundles, because a system does not know its
   process bundle when it programs the code.
4. The same derivation shows the static-code windows do not tile 10 – 166 MHz
   either: no single code is held in every bundle at 12.5 – 14.5, 21.0 – 24.4,
   34.0 – 43.7, 57.2 – 75.7 and 94.4 – 133.4 MHz. This record does not derate
   further on that finding (the ruling addressed the ceiling); it records it in
   the row's conditions, so frequencies there need the code re-selected as
   conditions move. The operator may wish to rule on it separately.
5. v2 auto-calibration (out of v1 scope per DR-003) remains the recorded route
   back to the full 10 – 200 MHz range for a static-configuration part.
6. The re-derivation is a checked-in script,
   `sim/vco-tuning-range/testbench/static_band_coverage.py`, with a known-answer
   test, `sim/tests/test_static_band_coverage.py`. Nothing is transcribed.

## Evidence

Output of `python3 sim/vco-tuning-range/testbench/static_band_coverage.py --check`
on the committed record `sim/vco-tuning-range/corners/20260804-162735-72883fb/raw_measures.csv`
(5 MOS bundles × 3 temperatures × 3 supplies = the 45-point matrix; pure
arithmetic, no simulation run):

```
VCO record 20260804-162735-72883fb; 45 PVT points (5 bundles x 3 T x 3 V)

Coverage of 200 MHz by a single static code (points reached, of 9 per bundle)
| bundle | band 6 | band 7 | any single code reaches all 9? |
|---|---|---|---|
| `typical` | 7 of 9 | 8 of 9 | **no** |
| `ff` | 6 of 9 | 9 of 9 | yes - band 7 |
| `ss` | 8 of 9 | 8 of 9 | **no** |
| `fs` | 7 of 9 | 8 of 9 | **no** |
| `sf` | 6 of 9 | 8 of 9 | **no** |

Over 45 points: 30 reached by band 6 or 7, 11 only by band 7, 4 only by band 6

Frequencies held by ONE static code over the whole box, per bundle
(union over codes of [max band floor, min band ceiling] across the 9 points, MHz)
- `typical`: 4.8-12.8; 13.2-21.5; 21.9-34.8; 38.9-58.5; 66.2-97.3; 117.1-173.3; 205.0-300.2
- `ff`: 4.5-34.3; 35.5-57.4; 59.7-94.4; 104.0-166.3; 182.6-285.1
- `ss`: 5.2-8.0; 8.6-12.9; 14.5-21.8; 24.4-35.7; 43.7-60.5; 75.7-102.1; 133.4-183.6; 225.4-315.5
- `fs`: 4.8-13.1; 13.2-35.6; 38.8-59.8; 66.1-99.7; 116.2-177.3; 202.0-305.2
- `sf`: 4.9-7.8; 8.0-12.5; 13.3-21.0; 22.1-34.0; 39.1-57.2; 66.7-95.2; 118.4-169.8; 208.1-295.0

Held by a static code in EVERY bundle: 5.2-7.8; 8.0-8.0; 8.6-12.5; 14.5-21.0; 24.4-34.0; 43.7-57.2; 75.7-94.4; 133.4-166.3; 225.4-285.1

Derated ceiling: highest frequency <= 200 MHz that one static code holds
| scope | derated ceiling (MHz) |
|---|---|
| `typical` alone | 173.3 |
| `ff` alone | 200.0 |
| `ss` alone | 183.6 |
| `fs` alone | 177.3 |
| `sf` alone | 169.8 |
| every bundle (the figure the Output band row carries) | 166.3 |

Derated ceiling: 166.3 MHz -> 166 MHz rounded down

Static-code holes below the ceiling, every bundle (MHz): 12.5-14.5; 21.0-24.4; 34.0-43.7; 57.2-75.7; 94.4-133.4

#534 finding re-derives
```

Over the 45 points, 30 are reached by band 6 or 7, 11 only by band 7 and 4 only
by band 6, so the union covers all 45 and no single code does.

## Alternatives considered

- **Keep 200 MHz as an envelope and add only a condition** — weaker than the
  operator's ruling; the headline would still over-promise to a system that
  cannot re-select the code.
- **Change the band map (overlap across the PVT box)** — a DR-003 revision with
  re-verification cost; not chosen.
- **Defer entirely to v2 auto-calibration** — leaves the v1 row unqualified.

## Consequences

- A v1 consumer needing 200 MHz must re-program the band code as conditions
  move (or accept the part is outside this row); the 742.5 MHz consumer row was
  already not met and is unaffected.
- `sim/reference-spur-band-top` and `sim/period-jitter-band-top` keep
  measuring each point in the band a part targeting 200 MHz at that point would
  use; that is correct for the envelope, but is not a claim that one part held
  200 MHz across the box.
- Any headline quoting "10 – 200 MHz" as a static promise is amended in
  `spec/pll.md`; measured numbers are untouched.
- On ratification the "pending" wording in `spec/pll.md` is dropped by the
  operator's ratification commit; until then the ratified text of the row is
  quoted alongside.
