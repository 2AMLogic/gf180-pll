# DR-013: T2′'s reach stays at 2× the Lock criterion — the window's PVT spread comes down instead, and T1′/T2′ are measured at the flag rather than at the delay chain

- **Status**: proposed, drafting for operator ratification via PR review — the
  same `2AMLogic/2am#357` ratification-via-PR route DR-007, DR-009 and DR-010
  record (a builder drafts the record on the evidence; the operator's PR
  approval is the ratifying act). Status stays `proposed` until that approval
  and merge.
- **Date**: 2026-09-16
- **Decided by**: Builder agent, issue #401
- **Revises**: `spec/pll.md`'s [Lock detector](../pll.md#lock-detector)
  section — the **verification definition** of targets T1′ and T2′, row 16's
  status, and gap 1's text. **Neither target's number changes**: T1′ stays
  ≥ 1 ns and T2′ stays ≤ 2 ns. Row 16 remains one of the two rows DR-007
  Amendment A1 carved out of ratification, and this record does not close that
  carve-out.
- **Consumes**: DR-010 (which decided T1′/T2′ and the W = 9.5 µm sizing this
  record evaluates), DR-012 (whose measured static-phase-offset evidence is
  what makes the reach question answerable), DR-002 Decision 4 (the lock
  flag's scope as a passive monitor).
- **Evidence**:
  - `sim/lock-detector/records/20260916-052313-b1633b5.md` — 185 points, the
    full 13-bundle PVT grid plus a phase-error ladder refined to 0.02 ns at
    `ff`/−40 °C/3.63 V and 0.1 ns at `ss`/125 °C/2.97 V, driving the **whole**
    lock-detector loop from a PFD-modeled UP/DN pair. Clean tree at
    `b1633b52b9fe3234e966056f6c30c3fafb87681d`. This is the first measurement
    of the W = 9.5 µm cell in situ (#393).
  - `sim/lock-window-sizing/records/20260915-202802-79c0cee.md` — DR-010's own
    sizing ladder, 1170 points, driving `delaywin_3v3` in isolation from an
    ideal voltage step. Its own header records it as **taken against a dirty
    working tree** and "not citable as a clean-tree result".
  - `sim/supply-sensitivity/records/20260916-051708-8cedbba.md` and
    `sim/pfd-deadzone/records/20260916-051356-8cedbba.md` — DR-012's evidence,
    used here only for the settled static phase offsets the flag has to
    observe.

## Context

DR-010 replaced T1/T2 with a two-sided band anchored on the ratified Lock
criterion — T1′ ≥ 1 ns, T2′ ≤ 2 ns, both at every point of the mandated grid —
and re-sized `delaywin_3v3`'s four `nfet_03v3` MOS-cap loads from W = 8 µm to
W = 9.5 µm to fit inside it. #393 implemented that sizing and re-characterized
it. T1′ is met. **T2′ is not shown to hold**, at the corner DR-010's own
ladder already names as T2′'s binding point.

### What the two campaigns actually measure, and why they disagree

They do not measure the same quantity, and that — not a modelling error, and
not simulator noise — is the whole finding.

`lock-window-sizing` measures `t_win`, the `ERR → ERRD` delay through the bare
chain. `lock-detector` measures that too, and reproduces it closely: at
W = 9.5 µm, **1.026 ns in situ against 1.017 ns isolated** at
`ff`/−40 °C/3.63 V (+0.9 %) and **1.965 ns against 1.956 ns** at
`ss`/125 °C/2.97 V (+0.5 %). The delay chain is not where the campaigns part
company.

`lock-detector` additionally measures the quantity T1′ and T2′ are *about*:
the largest phase error at the PFD inputs for which `lock` asserts and stays
asserted. That is **not** `t_win`. `WIDE = ERR · ERRD` is high for `terr −
t_win` — so a phase error just past `t_win` produces a WIDE pulse of a few
tens of picoseconds, and the `MDNW`/`VWIN` window-charge network cannot
discharge against the weak pull-up on a pulse that narrow. The flag therefore
keeps asserting for some further **δ** of phase error beyond `t_win`:

| Corner | `t_win` | flag still asserts at | flag does not assert at | δ = observable − `t_win` |
|---|---|---|---|---|
| `ff`/−40 °C/3.63 V (T1′ binds) | 1.026 ns | 1.04 ns | 1.06 ns | +0.014 … +0.034 ns (+1.4 … +3.3 %) |
| `ss`/125 °C/2.97 V (T2′ binds) | 1.965 ns | 2.0 ns | 2.1 ns | +0.033 … +0.138 ns (+1.7 … +7.0 %) |

δ is visible in the record as more than an edge location. At the T1′ corner
the assert time stretches from 0.680 µs at `terr` = 1.02 ns to 0.911 µs at
1.04 ns before the flag drops out at 1.06 ns — WIDE is already firing at
1.04 ns and merely losing the fight with the pull-up. At the T2′ corner the
assert time at `terr` = 2.0 ns (1.9126 µs) is **identical to seven digits** to
the assert time at 0.2 ns: at that slow corner a 35 ps WIDE pulse does nothing
measurable at all. δ is a real circuit term, it is larger at slow corners, and
an isolated-chain campaign structurally cannot see it.

So the gap between the two campaigns at the T2′-binding corner is **+0.044 …
+0.144 ns** (the in-situ observable, 2.0 … 2.1 ns, against the isolated
1.956 ns), of which ~0.01 ns is the delay chain and the rest is δ. #401's body
describes this as "roughly 0.1–0.2 ns"; the measured decomposition above is
the precise form, and its upper end is what that estimate captured. Either way
it is larger than the +2.2 % (0.044 ns) of T2′ margin DR-010 booked.

### How far outside the band the design actually is

The campaign bounds the T2′ edge to **[2.0, 2.1) ns** and no further: the
refinement ladder steps 2.1 → 2.9 ns and the coarse ladder's nearest point
below is 2.0 ns, so there is no measured point between them. The overrun is
therefore **0 … 5 %** and its size is genuinely unresolved — the only reading
under which T2′ holds is the exact boundary value, which this ladder cannot
distinguish from a 5 % miss.

That imprecision does not change the structural picture, which is what this
record decides on:

| Quantity | Isolated chain (DR-010's basis) | In situ (this record's basis) |
|---|---|---|
| Window at the T1′ corner | 1.017 ns | 1.04 … 1.06 ns |
| Window at the T2′ corner | 1.956 ns | 2.0 … 2.1 ns |
| PVT spread of `t_win` over the grid | 1.923 × | 1.929 × (1.0199 … 1.9678 ns) |
| PVT spread of the **observable** | not measurable | **1.89 … 2.02 ×** |
| Joint slack inside the 2 × band | +1.7 % / +2.2 % | **≈ 0 %** |

The band is satisfiable at all only while the spread stays under 2×. Measured
at the flag, the spread is 1.89–2.02× — it is not established to be under 2×
at all. Every erosion DR-010 named as unquantified (extraction, #18; device
mismatch, disabled in both campaigns) is still unquantified and still to come,
and one of the three — the driving edge rate, i.e. δ — has now been measured
and is worth up to 7 % by itself.

## Decision

**1. T1′ and T2′ are measured at the flag, not at the delay chain.** The
observable both targets bound is *the largest phase error at the PFD inputs
for which `lock` asserts and stays asserted*, measured through the assembled
lock-detector loop — `sim/lock-detector`'s `window_edges` table. `t_win` is a
useful proxy and a good sizing coordinate, but it is systematically optimistic
by δ, and δ is larger at exactly the corner where T2′ binds. No future claim
that T1′ or T2′ is met may rest on an isolated-chain measurement alone.
`sim/lock-window-sizing` is **not** invalidated — it remains the sizing ladder
— but it is no longer sufficient evidence for a T1′/T2′ verdict.

**2. T2′'s reach stays at 2 × the ratified Lock criterion. It is not
widened.** This is the first of the two moves DR-010 §Consequences pre-named,
and it is rejected on evidence that did not exist when DR-010 was written.

T2′ exists to bound false positives: the flag must not tell a consumer
"locked" about a part the ratified criterion excludes. DR-012 (2026-09-16)
measured, for the first time, how much static phase the loop actually stands
off in its own settled state — 1.227 ns at `ff`/27 °C/3.63 V and 1.049 ns at
`typical`/−40 °C/3.63 V, both **over** the ratified ≤ 1 ns bound,
systematic-only and before `mc-cp-mismatch`'s 0.576 ns statistical term. Put
the flag's own window at those same corners beside them:

| Corner | settled static phase (DR-012) | window at W = 8 µm | window at W = 9.5 µm |
|---|---|---|---|
| `typical`/−40 °C/3.63 V | 1.049 ns | 0.973 ns (7 % **below**) | 1.131 ns isolated / 1.140 ns in situ (8 % **above**) |
| `ff`/27 °C/3.63 V | 1.227 ns | 0.986 ns (20 % below) | 1.146 ns isolated / 1.155 ns in situ (6 % below) |

At W = 8 µm the flag's window sat below the loop's settled offset at both
corners and the flag refused to assert — which is the flag reporting
correctly, and `sim/supply-sensitivity`'s committed rows do carry `FAIL:lock`
at both. At W = 9.5 µm the window has risen **past** that offset at
`typical`/−40 °C/3.63 V and to within 6 % of it at `ff`/27 °C/3.63 V. The 2×
reach, at the sizing this design now carries, has already consumed nearly all
of the distance between the criterion and the loop's own measured misses of
it. Widening the reach spends distance the design does not have: it would
license the flag to assert on exactly the parts DR-012 identifies as the
design's real gap, and a flag that asserts there is not a conservative
observer, it is a wrong one.

Two further reasons, either sufficient on its own:

- The 2× reach was never derived from the achievable spread and must not now
  be re-derived *from* it. Moving a maximum until a measured result falls
  inside it is relaxing the specification to make the result pass, which
  CLAUDE.md forbids and which DR-010 and DR-012 each refused in their own
  alternatives.
- The number the reach would have to move to is not stable. With the spread
  itself unresolved at 1.89–2.02× and extraction and mismatch still
  unmeasured, any widened bound chosen today would be re-litigated by #18's
  re-take.

**3. T2′ is recorded as not met, and the size of the miss is recorded as
unresolved.** `spec/pll.md` row 16 and the Lock detector section state the
edge as bounded to [2.0, 2.1) ns — 0–5 % past budget — and the status word is
**not met**, because a target that cannot be shown to hold is not met. A
0.02 ns refinement of that corner's ladder between 2.00 and 2.10 ns (9 points,
the same mechanism the campaign already runs at the T1′ corner, on the
existing deck) is owed and is listed in [Verification
owed](../pll.md#verification-owed). It sizes the miss; it cannot clear it,
because the structural finding in Decision 4 does not depend on where in that
interval the edge lands.

**4. The fix is a lower-spread window, and this record states the target it
has to hit.** This is the second move DR-010 pre-named, and it is chosen. Any
replacement for `delaywin_3v3`'s open-loop inverter-chain-into-MOS-cap delay
must hold the **observable** window (Decision 1) to a PVT spread of
**≤ 1.65 ×** over the mandated grid, which is what a 2× band with 10 % of
margin on each edge requires: 2 / 1.1² = 1.65.

10 % per edge is derived, not rounded to: δ alone — one of the three erosions
DR-010 listed as unquantified — measures up to 7 % at the binding corner, and
extraction (#18) and mismatch are still unmeasured. A per-edge margin smaller
than the largest single erosion already measured is not a margin. Today's
design is at ≈ 0 % against that target on both counts, and **no sizing of the
present topology can reach it**: the spread is a property of the chain, not of
its sizing (1.928× at W = 8 µm, 1.906× at W = 26 µm — a 3.25× sizing change
buys 1 % of spread).

**5. Which lower-spread mechanism is not decided here; its implementation is
scoped to #407.** Two routes are on the table and this record deliberately
picks neither, on the DR-012 Decision 7 pattern (decide the axis the fix must
act on; do not pick the circuit without the evidence to pick it):

- **A bias-referenced delay** — bandgap- or replica-biased, so the delay is
  set by a current that does not track the inverter's own drive. It attacks
  process, voltage and temperature together. Its own achievable spread in this
  PDK is unmeasured, and it adds an analog block to a cell whose simplicity
  DR-010 called deliberate.
- **A trimmed delay** — a fixed trim code set once at test, in the same idiom
  as the existing [Icp trim rule](../pll.md#icp-trim-code-rule), *not* a
  self-calibration FSM (DR-002 Decision 4's scope boundary is intact). It
  removes the process axis, and with it extraction error and global mismatch,
  post-silicon. What remains is the voltage/temperature spread **within** a
  process bundle, which this record's evidence measures directly: **1.453×**
  (`ff`), 1.481× (`sf`), 1.491× (`typical`), 1.502× (`fs`), **1.513×** (`ss`).
  Adding the quantization of a trim step (the ladder's 0.5 µm step is worth
  4.6–4.8 % of window, so ±2.4 % if trimmed to the nearest step) gives ≈ 1.55×
  — inside Decision 4's 1.65 × target, with ≈ 13 % per edge. Its cost is not
  in the cell: it is a trim code, its storage, and a test-time measurement of
  a 1–2 ns delay, all of which are block-interface questions outside the lock
  detector.

That second route matters beyond itself: it is measured, committed evidence
that Decision 4's target is **reachable**, which is what makes refusing to
widen the band in Decision 2 a design decision rather than a wish.

**6. Nothing else moves.** T1′ stays ≥ 1 ns. T3, T4 and T5 are untouched. The
ratified Lock criterion is untouched (DR-012 Decision 1 stands).
`delaywin_3v3` stays at **W = 9.5 µm as drawn** — this record does not re-size
and does not revert #393: W = 9.5 µm is the sizing with the largest T1′ margin
of any candidate that is not already past T2′, reverting it would re-open the
false-negative failure DR-010 fixed, and any replacement under Decision 4
re-opens the sizing question from scratch anyway. Row 16 stays inside DR-007
Amendment A1's carve-out.

**7. `sim/lock-time`'s 270-run cold-start grid re-take stays held.** DR-010's
"Downstream" note already owed it. It is not released by this record: its
PASS/FAIL verdicts are taken against the design's own `lock_detector`, so a
grid re-taken now would be interpreted against a window that Decision 4 says
is going to change. It is released when #407 lands a window that meets
Decision 4's target, not before.

## Alternatives considered

- **Widen T2′'s reach to whatever clears the measurement (2.1 ns, 2.5 ×, …).**
  Rejected — Decision 2, at length. The short form: the reach is a maximum on
  false positives, the design's *measured* false-positive headroom at the
  current sizing is already 8 % negative at one corner and 6 % at another
  against DR-012's settled offsets, and the number would be chosen to fit a
  result rather than derived from a requirement.
- **Tighten T2′ instead, since DR-012 suggests 2× is already generous.** Not
  chosen *now*, and named so a future record does not have to rediscover it.
  It is the direction the evidence points, but it cannot be acted on before
  Decision 4's fix: T1′ is pinned at 1 ns by the no-false-negative argument,
  so the band's width is bounded below by the achievable spread, and on the
  measured within-bundle numbers in Decision 5 nothing below ≈ 1.5 × is
  reachable even with a perfect process trim. Tightening the reach before
  narrowing the spread would specify a band no candidate can satisfy.
- **Re-size once more (W = 9.2 … 9.4 µm), splitting the difference.**
  Rejected, on DR-010's own guidance and on arithmetic. With the observable's
  spread at 1.89–2.02 × against a 2 × band there is at most 5.5 % of joint
  slack to divide between two edges and possibly none; T1′'s in-situ margin is
  +4–6 %, so any downsize large enough to be resolvable buys T2′ margin out of
  T1′'s at roughly 1:1. The ladder's own resolution makes this concrete: one
  0.5 µm step moves the window 4.6–4.8 %, which is the entire T1′ margin.
- **Scale `MCW` / the `VWIN` window-charge network to shrink δ.** Rejected as
  a fix for the band, and it **refines rather than contradicts** DR-010
  Decision 3. DR-010 held that scaling the integrating capacitor "moves no
  phase threshold at all"; the in-situ evidence shows that is very nearly, but
  not exactly, true — the network sets δ, and δ is 1.4–7 % of the observable
  threshold. But δ is *all* it sets. Driving δ to zero would still leave
  `t_win`'s own 1.929 × spread against a 2 × band, i.e. ≤ 3.5 % of joint slack
  and still nothing for extraction or mismatch. It is worth doing as part of
  #407's work, and it is not a route to Decision 4's target on its own. DR-010
  Decision 3's operative conclusion — that the phase threshold is the delay
  and the capacitor is T4's subject — stands.
- **Wait for #18's extracted-parasitic re-take before deciding anything.**
  Rejected: the *direction* of that erosion is already known — extracted wire
  capacitance adds delay, which pushes the T2′ edge further out, not back in —
  so waiting cannot clear T2′ and can only make the miss bigger. Meanwhile
  #163's `sim/lock-time` grid and row 9's ratification sit behind row 16's.
- **Leave row 16 as it is and carry the gap another revision.** Rejected on
  the same grounds DR-010 rejected it: "recorded rather than papered over" is
  the right answer for one revision, not a resting state. The difference now
  is that the gap is no longer a sizing question anyone can re-open — Decision
  4 makes it a topology question with a numeric acceptance target, which is
  something a follow-up issue can actually be scoped against.

## Consequences

- **`spec/pll.md` changes in five places, none of them a target's number**:
  the Lock detector target table (T2′'s rationale records that the reach was
  re-derived and left alone, and a new paragraph defines the observable per
  Decision 1), the "Measured behaviour" table (the observable and `t_win` are
  reported as the distinct quantities they are, and the observable's spread is
  reported beside them), gap 1 (restated as a decided outcome rather than an
  open question), row 16 (target wording plus status), and two [Verification
  owed](../pll.md#verification-owed) rows — the Lock-detector row gains the
  0.02 ns refinement and the #407 pointer, and the Lock-time row records the
  hold in Decision 7. `sim/CHARACTERIZATION.md`'s `lock-detector`,
  `lock-window-sizing` and lock-detector coverage rows are re-pointed the same
  way; no committed record is edited.
- **Row 16 does not leave DR-007 Amendment A1's carve-out**, and this record
  does not pretend otherwise. T2′ is not met, T4/T5 below 25 MHz are still
  uncharacterized, and row 9 stays behind row 16.
- **The design's `lock` flag is, today, a marginal observer at two corners and
  a wrong one at one.** That is worse news than #401 as filed contained, and
  it is a consequence of the fix DR-010 decided, not of the original defect:
  at W = 8 µm the flag under-asserted (a false negative on a locked part), and
  at W = 9.5 µm it has crossed `typical`/−40 °C/3.63 V's settled 1.049 ns
  offset in the other direction. **This crossing is inferred across two
  campaigns, not measured in one loop** — every committed
  `sim/supply-sensitivity` row is at W = 8 µm, and its f_ref (12.5 MHz)
  differs from `sim/lock-detector`'s (25 MHz). The comparison is legitimate
  because the window is an absolute time (`spec/pll.md` says so explicitly)
  and because DR-012 measured the offset's f_ref sensitivity as small (−6.4 %
  for a 2× change, which would put the 25 MHz-equivalent offset at ≈ 1.12 ns
  against a 1.140 ns window — still crossed, but by 2 % rather than 8 %).
  Confirming it in one deck needs `sim/supply-sensitivity` re-run at
  W = 9.5 µm, which is named in #407's scope.

  > **Follow-up (#417, 2026-09-20): this has since been measured in one loop,
  > and both cells came out as inferred.** The paragraph above is left as
  > written — it was the state of the evidence when this record was ratified,
  > and the reasoning it records (why the cross-campaign comparison was
  > legitimate, and by how much f_ref moved the answer) is what a reader needs
  > to judge how much the confirmation was worth. What has changed is that it
  > is no longer the best evidence available.
  >
  > `sim/supply-sensitivity/records/20260920-180604-0f91a9b.md` §1d re-makes
  > the comparison with **both halves out of the same closed-loop transient**,
  > at one f_ref (12.5 MHz), at the **trimmed** `delaywin_3v3` DR-014 decided
  > and #411 built, with each bundle at the code the
  > [trim-code rule](../pll.md#lock-detector-window-trim-code-rule) selects
  > for it — which is the window a real part of that bundle carries, not the
  > W = 9.5 µm untrimmed cell this paragraph reasoned about:
  >
  > | Cell | code | settled offset | `lock` | window vs. offset, in loop | vs. this record |
  > |---|---|---|---|---|---|
  > | `typical`/−40 °C/3.63 V | 7 | 0.8135 ns | 3.63 V (asserted) | **above** | crossed → **confirmed** |
  > | `ff`/27 °C/3.63 V | 11 | 1.233 ns | 6.9 nV (not asserted) | **at-or-below** | not-crossed → **confirmed** |
  >
  > So Decision 4's verdict — "a marginal observer at two corners and a wrong
  > one at one" — survives the trim and no longer depends on reading two
  > campaigns against each other. The `ff`/27 °C/3.63 V row is the "wrong
  > observer" case caught in the act: the loop is frequency-locked to
  > 100.003 MHz with a settled 1.233 ns offset and the flag never rises.
  >
  > **What that follow-up does not do.** It is a declared two-cell subset —
  > the two cells this paragraph names and no others — so it re-points the
  > crossing question only. Every other cell of `sim/supply-sensitivity` is
  > still at the untrimmed window, and that campaign's PVT statement is still
  > `20260901-155456-46b92f8`. A trimmed-window full-grid re-run is
  > **#437**.
- **`sim/lock-time`'s 270-run re-take stays held** (Decision 7), and so does
  any interpretation of #163's 233 FAILs against a specific window.
- **Nothing in `sim/` is invalidated and no design file changes.** This record
  edits specification text only. `sim/lock-window-sizing`'s ladder keeps its
  value as a sizing coordinate under Decision 1; its own dirty-tree provenance
  caveat is a second, independent reason to prefer the in-situ record where
  the two disagree, and the caveat is the source record's own, not this
  record's reading of it.
- **What is still not known, stated plainly**: where in [2.0, 2.1) ns the T2′
  edge actually sits; what δ, the spread, or either edge does after extraction
  (#18) and with mismatch enabled; what spread a bias-referenced delay would
  achieve in this PDK; and whether a trim code is affordable in the block's
  pin/DFT budget, which is not a lock-detector question. Decisions 4 and 5 are
  sized so that none of those answers changes the direction — only which route
  #407 takes.
