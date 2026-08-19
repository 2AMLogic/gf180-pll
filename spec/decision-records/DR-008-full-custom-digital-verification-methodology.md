# DR-008: Full-custom digital-partition verification methodology (T1/bronze Digital-column interpretation)

- **Status**: proposed
- **Date**: 2026-08-19
- **Decided by**: Builder agent, issue #148, drafting for operator ratification
  via PR review — per the 2026-08-19 standing policy recorded on #148
  ("canary spec/DR ratification-via-PR ... a builder drafts the
  ratification/DR as a PR on the evidence, and the operator's PR approval is
  the ratification act"; policy source `2AMLogic/2am#357`, not readable from
  this repo's checkout — cited as recorded on #148, not independently
  verified against that repo). Per that policy, this record's Status stays
  `proposed` until this PR is approved and merged; the approval/merge is the
  ratifying act, and the Status line should be updated to `ratified` as part
  of it.
- **Related**: #142 (T1/bronze re-read that first raised this as an open
  methodology question, items 1/2/5/7), #143 (decomposition of #142's
  failing/caveated items into dispatchable issues), #148 (this record's
  source issue), DR-002 Decision 3 (device-flavor / no-standard-cells
  rationale this record extends into verification methodology)

## Context

#142's T1/bronze checklist re-read flagged a methodology gap affecting items
1, 2, 5, and 7 of `klayout-tools`' `docs/design-evidence-tiers.md` T1
checklist: those four items are the ones whose required artifact differs by
block kind (Analog vs. Digital column), and this repo's digital partition —
the feedback divider (`design/divider_chain.sch`, `design/div23_cell.sch`),
the lock detector (`design/lock_detector.sch`), and the shared static-CMOS
logic library they're built from (`design/inv_3v3.sch` etc.) — cannot
satisfy the Digital column as written. That column assumes an RTL/synthesis
flow: item 1 wants "committed RTL sources plus the synthesized gate-level
netlist," item 2 wants "committed routed GDS/OASIS from place-and-route,"
item 5 wants "multi-corner static timing analysis ... plus a bit-exact
functional test suite," item 7 wants "the functional test suite re-run
against the post-route gate-level netlist with back-annotated SDF timing."

This repo has zero RTL (`*.v`/`*.vhd`: zero hits) and no synthesis flow, by
deliberate design-wide decision. `design/README.md`, restating DR-002
Decision 3's rationale: the two open gf180mcu standard-cell libraries for
this node are 5 V-flavor and this design is 3.3 V thick-oxide-only, so they
were never usable here — every logic gate, digital or analog, is a
hand-captured full-custom xschem schematic. The digital partition is
therefore verified exactly like the analog partition: SPICE simulation
across the PVT corner matrix, not STA against a gate-level netlist. It is
not that the digital partition lacks Digital-column evidence — it is that
the Digital column names artifacts (RTL, synthesized netlist, SDF) that this
partition's own design flow never produces, by construction, independent of
how much verification work is done.

This is a narrower case than the one `klayout-tools#636` already fixed.
#636 gave the tier doc Analog/Digital columns at all, for digital blocks
built through this toolkit's synthesis path (`klt synthesize`, `klt
place-and-route`) that previously had no non-analog column to satisfy
(`sky130-modexp`, the digital half of `gf180-trng`, etc.) — every example
that motivated #636 has RTL. This record is about the opposite shape: a
digital *partition inside a mixed-signal block* that has no RTL at all and
never will, because the block's own device-flavor decision (DR-002 Decision
3) made a synthesis flow unusable here. #636's Digital column doesn't fit
that case any better than the pre-#636 doc fit a synthesized digital block —
it just names a different set of unproducible artifacts.

Candidate framings weighed (from #148, not exhaustive):

1. Full-custom SPICE-PVT-sweep verification counts directly as-is
   ("PASS-by-analogy," #142's interim practice).
2. The Digital column's literal artifacts (STA, SDF) are required as
   written; a full-custom digital partition needs an upstream tier-doc
   amendment before it can be scored at all.
3. A hybrid: the Digital column's *artifacts* don't apply, but the
   *verification obligation* each item encodes still does, discharged by a
   named full-custom equivalent — the Analog-column artifact for that item,
   plus (where the Digital column protects something the Analog column
   doesn't check for free, e.g. setup/hold-style timing margin) an explicit
   named substitute metric.

## Decision

**Framing 3 (hybrid) is adopted**, scoped to this repo's digital partition
as defined above (feedback divider, lock detector, and the shared 3.3 V
static-CMOS logic library instantiated only by those two blocks), for T1
checklist items 1, 2, 5, and 7 only. Item 6 is unaffected (it is not
column-differentiated in the checklist text, and neither the divider nor the
lock detector class as statistical spec rows). Items 3, 4, 9, 10 are already
kind-independent per the checklist and are untouched.

For this repo's digital partition, each item's Digital-column artifact is
**replaced** by the following full-custom equivalent — this is a
substitution, not a waiver: an item that is not satisfied by a genuine,
freshness-checked artifact under this mapping still FAILs, exactly as it
would under the literal Digital column.

- **Item 1 (design sources)**: satisfied by the Analog-column artifact
  applied to the digital partition — committed schematic sources
  (`divider_chain.sch`, `div23_cell.sch`, `lock_detector.sch`,
  `dff_tg_3v3.sch`, the shared static-CMOS cells) plus the netlist
  regenerated on design change, checked by `design/netlist.sh --check`
  (enforced in CI's `pdk-checks` job). This matches #142's existing
  "PASS-by-analogy" practice for item 1 — this decision ratifies that
  practice rather than changing it.
- **Item 2 (layout)**: satisfied by the Analog-column artifact applied to
  the digital partition — committed GDS/OASIS for the hand-drawn full-custom
  digital-partition layout, reproducibly generated or with documented
  provenance. The Digital column's P&R-flow requirement does not apply:
  there is no gate-level netlist to place-and-route. This does not change
  today's status — no PLL-block layout exists yet (analog or digital
  partition), so item 2 remains FAIL either way; this decision only fixes
  which artifact will eventually clear it for the digital partition.
- **Item 5 (full corner verification vs. a ratified spec)**: satisfied by
  the Analog-column artifact — PVT corner-matrix SPICE simulation covering
  every digital-partition spec row at its bound corners, with per-row
  pass/fail and the binding corner recorded — **plus** an explicit named
  substitute for the timing-margin check the Digital column's STA
  requirement protects: a margin metric measured directly in the same
  transient/AC sweep, reported per PVT corner. This repo already collects
  exactly that, and it predates this decision: the divider chain's
  `retiming_margin` derived table (`sim/divider-ratio-chain/records/`,
  e.g. `20260802-100727-082c879.md`) computes
  `setup_margin_s = T_vco - t_arr_s - tsetup_s` and
  `hold_margin_s = t_arr_s - thold_s` per PVT point at the chain's own
  worst-case corner (N=64, 200 MHz) — a direct SPICE-measured analog of
  STA setup/hold margin, joined against per-PVT `tsetup`/`thold` from
  `sim/divider-ratio-dff`. The lock detector's `window_edges` derived table
  (`sim/lock-detector/records/`, e.g. `20260802-050119-c24ee3a.md`)
  computes the measured assert/deassert phase-error boundary per corner —
  the equivalent margin metric for that block. A digital-partition item-5
  verdict requires citing this kind of per-corner margin evidence, not only
  a functional pass/fail; a bare functional PVT sweep with no margin metric
  does not satisfy item 5 under this mapping.
- **Item 7 (post-layout verification)**: satisfied by the Analog-column
  artifact — the same spec suite (including the item-5 margin metric above)
  re-run against the netlist extracted from the digital partition's actual
  drawn layout, once that layout exists — exactly as for the analog
  partition, not a post-route gate-level netlist with back-annotated SDF
  (there is no route step). Today this item remains FAIL for both
  partitions on identical grounds (no PLL layout exists at all); this
  decision changes only which extraction/re-sim artifact will eventually
  satisfy it for the digital partition. The divider-chain record's own
  Limitation field already anticipates this: it flags its schematic-level
  `retiming_margin` as "an upper bound on the post-layout margin, not an
  estimate of it" and names itself as the record #18-class post-layout work
  must re-take — i.e. re-running that same derived-margin methodology
  post-layout is already the intended path, not a new obligation invented
  here.

This mapping is scoped to this repo's own digital partition, as identified
above. It is not a general amendment to `klayout-tools`' tier doc — see
"Consequences" for the friction issue filed against that gap.

## Alternatives considered

- **Framing 1 — accept full-custom SPICE-PVT verification as-is, no named
  substitute.** Rejected. This is #142's current interim practice and isn't
  wrong on the facts it checks, but it lets the digital partition
  permanently skip the one thing the Digital column's STA requirement is
  actually protecting — a timing-margin claim, not just a functional
  pass/fail — even though this repo already collects a full-custom
  equivalent for the two items where it matters (`retiming_margin`,
  `window_edges`). Ratifying "PASS-by-analogy" with no margin requirement
  would make item 5's digital-partition verdict weaker evidence than what
  this repo's own testbenches already produce.
- **Framing 2 — require the literal Digital-column artifacts, or treat the
  digital partition as unratable until `klayout-tools`' tier doc is amended
  upstream.** Rejected. `klayout-tools#636` already shows this class of
  cross-repo tier-doc question does not resolve quickly (it took a
  dedicated fleet-wide epic), and there is no forcing function guaranteeing
  a full-custom-specific amendment lands on any particular timeline. Holding
  this repo's digital-partition T1 items at a permanent, unconditional FAIL
  in the meantime — even where genuinely equivalent, already-collected
  evidence exists (the margin tables above) — mistakes "the upstream doc
  hasn't been updated yet" for "no evidence exists," which isn't true here.
- **A repo-local waiver with no named substitute metric (a looser version of
  framing 1, scored PASS on functional-only PVT evidence).** Rejected for
  the same reason as framing 1, more directly: without requiring the margin
  tables, this alternative would score item 5 PASS on evidence no stronger
  than "the divider counted correctly at every corner," dropping the
  setup/hold-style claim entirely rather than substituting an equivalent
  for it.

## Consequences

**In scope now:**
- #142-class T1/bronze re-reads for this block can score items 1, 2, 5, 7 on
  the digital partition under this named mapping instead of flagging them as
  an open methodology question every time. Item 1 stays PASS (already true
  under #142's interim practice). Items 2 and 7 stay FAIL — this decision
  does not manufacture evidence that doesn't exist, it only fixes which
  future artifact clears them. Item 5's digital-partition sub-verdict now
  has an explicit evidentiary bar (per-corner margin metric, not just
  functional pass/fail) that the existing `retiming_margin` and
  `window_edges` tables already meet, for the corners they cover — a future
  re-read should check corner *coverage* against this bar (e.g. whether
  `retiming_margin` is computed only at the N=64 worst case, not the full
  N=4..64 grid) rather than treating item 5 as an unscoreable open question.
- No `spec/pll.md` row changes. This decision is about which artifact
  discharges a T1-checklist item for the digital partition, not about any
  spec-table value.

**Explicitly not decided here:**
- Whether `klayout-tools`' `design-evidence-tiers.md` itself should gain a
  general full-custom-digital mapping. That is a cross-repo, shared-artifact
  question exactly like the one #636 already resolved for synthesis-based
  digital blocks — it belongs with the doc, not with one canary's decision
  record. Per CLAUDE.md's friction protocol, this record's shipping PR also
  files a generic tool-gap issue,
  `2AMLogic/klayout-tools#1190`, describing the gap (a full-custom, non-RTL
  digital partition has no evidence mapping in the current Digital column,
  which — post-#636 — assumes an RTL/synthesis flow) without restating this
  repo's specific ruling as the answer; that repository's own process
  decides whether/how to generalize it.
- No grant. `product/everyblock/grants.md` remains the sole authoritative
  record of bronze/T1 status, per #142's own guardrails; this record changes
  only how items 1/2/5/7 are graded for this block's digital partition, not
  whether a grant is recorded.
