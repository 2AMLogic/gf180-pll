# DR-041: The Area row is held at ≤ 0.30 mm²; the assembled `pll_top` (0.4078 mm²) is recorded as unmet and bounded compaction is authorized

- **Status**: proposed, drafting for operator ratification via PR review. The
  disposition itself (hold the row, record the miss, authorize a bounded
  feasibility study) was ruled by the operator on issue #758 on 2026-10-15.
  Status stays `proposed` until that approval and merge.
- **Date**: 2026-10-15
- **Decided by**: Builder agent, issue #758 (disposition ruled by the operator
  on the issue)
- **Revises**: nothing is rewritten. DR-016 and DR-017 stay as historical
  evidence; this record exercises the revisit trigger in DR-017 Decision 3
  (an assembled `pll_top` measuring the top-level overhead) and chooses to
  **hold** rather than amend.

## Context

The first assembled `pll_top` (issue #297,
`layout/evidence/pll-top-layout/PROOF.md`) measures **407,776.2 µm²
(0.4078 mm²)**, a 1317.66 × 309.47 µm bounding box, against a block sum of
183,964.4 µm² (loop filter as drawn): a measured top-level overhead of
**×2.217**. The row was sized to a ×1.25 ROM factor and holds only to
×1.664. `layout/floorplan/PLL-FLOORPLAN.md` §5's fail-loud clause has fired
(§5.16). This is a comparison of the committed documents' recorded figures,
not a new GDS measurement; no layout was re-measured for this record.

The 0.2254 mm² figure that `spec/pll.md` and DR-016/DR-017 carry is the
block-sum estimate (blocks × the unmeasured ×1.25 factor), not an assembled
result. The 40 µm domain spacing and 15 µm VCO keep-out behind part of the
gap are planning values from `floorplan/skeleton.py`, not foundry rules.

## Decision

1. **The Area row stays at ≤ 0.30 mm².** The limit and its margin are
   unchanged.
2. **The row is recorded as unmet as assembled**: 407,776.2 µm² (0.4078 mm²),
   135.9 % of the row. It stays unmet until qualifying evidence exists, i.e. a
   committed assembled `pll_top` GDS whose bounding box is ≤ 0.30 mm². The
   0.2254 mm² block-sum figure remains labelled as the block-sum estimate and
   does not satisfy the row.
3. **A bounded compaction feasibility study is authorized** (tracked as #792),
   focused on the divider-chain aspect ratio and the planning spacings. It may
   fail to recover the 35.9 % excess; this record makes no promise that it
   will.
4. **Any upward amendment of the limit needs a separate decision record**
   with an explicit operator-chosen new limit and margin. This record does not
   pre-authorize one.
5. This record exercises DR-017 Decision 3's trigger and does not touch its
   other parts. No other spec row changes, and no DRC/LVS verdict is claimed.

## Alternatives considered

- **Stage it: record the miss, study, then decide on amendment** — buys
  evidence either way but adds a second decision and delays closure compared
  with holding now; the study in Decision 3 gives the same evidence without
  deferring the status.
- **Amend the row upward on the assembled measurement** — aligns the spec with
  today's layout fastest, but accepts the overhead before any removable cost
  (aspect ratio, planning spacings) has been explored, and needs a new
  operator-chosen limit and margin.

## Consequences

- `spec/pll.md` row 15 and `## Area` report the row as unmet as assembled and
  cite this record; `manifests/integrator.json` and
  `docs/chipalooza/challenge-5-proposal.md` agree.
- The integration requirement is preserved; the cost is layout work (#792)
  with no guarantee of reaching 0.30 mm². If it does not, a later record must
  amend the limit.
- Until then the block cannot claim to meet its area target, which is
  visible in every downstream document rather than hidden behind the
  block-sum estimate.
