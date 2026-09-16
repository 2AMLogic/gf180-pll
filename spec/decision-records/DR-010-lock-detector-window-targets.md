# DR-010: Lock detector window targets — anchor T1/T2 on the ratified Lock criterion, and re-size `delaywin_3v3` to W = 9.5 µm

- **Status**: proposed, drafting for operator ratification via PR review — the
  same `2AMLogic/2am#357` ratification-via-PR route DR-007 and DR-009 record
  (a builder drafts the record on the evidence; the operator's PR approval is
  the ratifying act). Status stays `proposed` until that approval and merge.
- **Date**: 2026-09-15
- **Decided by**: Builder agent, issue #387 (finding 1)
- **Revises**: `spec/pll.md`'s [Lock detector](../pll.md#lock-detector)
  section — targets **T1** and **T2**, and the "two gaps" text under them.
  Row 16 of the target table is one of the two rows DR-007 Amendment A1
  carved out of ratification; this record is the first half of closing that
  carve-out (the other half, T4/T5 below 25 MHz, is untouched here and stays
  open).
- **Evidence**:
  `sim/lock-window-sizing/records/20260915-202802-79c0cee.md` — 1170 points,
  10 `delaywin_3v3` MOS-cap sizings × the full 13-bundle, 117-point PVT grid.
  Consumes `sim/lock-detector/records/20260802-050119-c24ee3a.md` (#11, the
  committed characterisation this campaign's control reproduces),
  `sim/supply-sensitivity/records/20260915-124108-49f539f.md` and
  `.../20260915-105055-2d6ab99.md` (#389/#384, the independent corroboration
  at `ff`/125 °C/3.63 V that prompted #387), and
  `sim/lock-time/records/20260831-052456-effc505.md` (#163, whose 233 of 270
  FAILs DR-007's post-ratification note already attributes largely to this
  unwidened window).
- **Followed by**: **DR-013** (#401), which records what happened when
  Decision 2's sizing was implemented (#393) and measured *in situ* rather than
  on the isolated delay chain this record's evidence drives: T1′ is met, T2′ is
  not shown to hold, and the choice §Consequences pre-named — "either a wider
  stated reach for T2′ … or a lower-spread delay reference" — is taken in
  favour of the latter, with the reach left at 2×. **Nothing in this record's
  Decisions is changed there**, and its targets are not edited in place;
  Decision 3's "scaling [`MCW`] moves no phase threshold at all" is *refined*
  (the network sets a small residual δ on the observable threshold, 1.4–7 %,
  and nothing else), not reversed, and Decision 2's W = 9.5 µm sizing stands as
  drawn. Read DR-013 before sizing any further work off this record's margins.

## Context

`spec/pll.md` row 16 states two targets for the lock detector's phase-error
window and, in the same breath, records that the design does not meet them:

> T1 — assert window ≥ **2.5 ns** of phase error at the PFD inputs …
> T2 — assert window ≥ **2× the worst-case static phase offset** …
> The window is 0.877–1.702 ns … **A correctly locked part may fail to
> assert `lock`.** The fix is geometric (widen the delay window, or scale the
> integrating capacitor), not architectural.

#384/#389 then found the same gap from a completely different campaign: after
a 3.30 → 3.63 V supply step, `ff`/125 °C/3.63 V does not assert `lock` even
in its **own undisturbed steady state** at the same rail. That is what #387
asks to be decided rather than re-disclosed.

Working the numbers turns up something the prose above does not say: **T1 and
T2, taken literally, make the `lock` flag a *worse* observer of the ratified
Lock criterion, not a better one.** `spec/pll.md`'s Lock criterion is `static
phase error at the PFD inputs ≤ 1 ns`, and its own rationale says the 1 ns
bound "is set where the lock detector's measured window sits … so the
criterion and the on-chip observable are describing the same event rather
than two different ones". T1 is a **minimum** on the window; the requirement
that the flag not assert far outside the criterion is a **maximum** on it;
and the delay chain's PVT spread is a fixed ≈1.92× that geometry cannot
change. Those three facts do not fit together, and the campaign measures by
how much they do not:

| Sizing | window over 117 corners | meets T1 (≥ 2.5 ns everywhere)? | worst-corner window ÷ the 1 ns criterion |
|---|---|---|---|
| W = 8 µm (as drawn) | 0.8746 … 1.686 ns | no | 1.69× |
| W = 9.5 µm | 1.017 … 1.956 ns | no | 1.96× |
| W = 26 µm | 2.584 … 4.924 ns | **yes** | **4.92×** |

So the smallest sizing that satisfies T1 at every corner is W = 26 µm, and it
buys that by letting the flag assert on a part **4.9× outside the very
criterion the flag exists to observe**. T1's stated rationale — "it must be
wider than the worst-case static phase offset the loop actually stands off in
lock" — is sized against a quantity (≈1.49 ns summed) that is *itself already
outside* the ratified ≤ 1 ns criterion. A part standing off 1.49 ns is, by
the ratified definition, **not locked**; a flag that refuses to assert there
is correct, not defective.

## Decision

**1. T1 and T2 are replaced by a two-sided band anchored on the ratified Lock
criterion.** The new targets, both of which must hold at **every** point of
the mandated PVT grid simultaneously:

| # | Target | Rationale |
|---|---|---|
| T1′ | Assert window ≥ **1 ns** — the ratified [Lock criterion](../pll.md#lock-time) itself | a part that *meets* the criterion must always be able to assert `lock`; a window narrower than the criterion at any corner is a false negative on a genuinely locked part |
| T2′ | Assert window ≤ **2 × the ratified Lock criterion** (2 ns) | the flag must not assert far outside the criterion it observes; 2× is the stated reach, and it is the direction whose failure is unsafe for a consumer gating logic on `lock` |

T3 (hysteresis ≥ 25 % of the assert window), T4 and T5 are unchanged by this
record.

**2. `delaywin_3v3`'s four MOS-capacitor loads change from W = 8 µm to
W = 9.5 µm** (L = 2 µm, `nfet_03v3`, count and topology unchanged). Measured:
1.017 … 1.956 ns over all 117 corners, `in-band` by T1′/T2′ with +1.7 % and
+2.2 % of margin, and bracketed on both sides by W = 9 µm (falls below T1′)
and W = 10 µm (crosses T2′), so the value is interpolated from measured
points rather than extrapolated.

**3. "Scale the integrating capacitor" is rejected as a fix for this gap.**
`design/lock_detector.sch`'s own signal-path note settles it: `WIDE = ERR ·
ERRD` is high only when the error pulse outlasts the `ERR → ERRD` delay, so
the **phase threshold is that delay and nothing else**. `MCW` (the
integrating MOS capacitor on `VWIN`; the issue text calls it `XMCW`, but the
instance as drawn is `MCW`, W = 30 µm / L = 6 µm) together with `MUPW`/`MDNW`
sets how many out-of-window pulses it takes to deassert and how long the weak
pull-up needs to re-assert — the assert/deassert **time constants**, which are
T4's subject, not T1/T2's. Scaling it moves no phase threshold at all.
`spec/pll.md`'s "widen the delay window, **or** scale the integrating
capacitor" offered these as alternatives; they are not.

**4. `ff`/125 °C/3.63 V's 1.796 ns static phase error is NOT a lock-detector
defect and is not fixed by this record.** At that corner the *loop* stands
off 1.796 ns of static phase in undisturbed steady state
(`supply_steady.csv`, `ff,125,3.63`) against a ratified criterion of 1 ns.
The part does not meet the Lock criterion at that corner, and the detector
refusing to assert is the flag **reporting correctly**. Widening the window
far enough to cover it would make the flag lie, which is precisely the
"relax the ratified spec to make results pass" that CLAUDE.md forbids. This
is routed to **#394** as a charge-pump / static-phase-offset question, not
carried here.

**5. Implementation is deferred.** This record decides; it does not edit
`design/delaywin_3v3.sch`. The sizing change invalidates every committed
`sim/lock-detector` record, the `lock_detector` block layout and its device
tests, and needs a full T1′–T5 re-characterisation to land — scoped to **#393**, gated
on this record being ratified.

## Alternatives considered

- **Widen to W = 26 µm and satisfy T1 as written.** Rejected: measured, it
  puts the worst-corner window at 4.924 ns, so the flag would assert on parts
  up to 4.9× outside the ratified Lock criterion. That is a false-positive
  lock indication in the direction `design/lock_detector.sch`'s "slow to rise,
  quick to fall" asymmetry was chosen to avoid. It also costs 3.25× the
  capacitor area for a worse observable.
- **Scale `MCW` / the `VWIN` integrating capacitor.** Rejected on topology —
  see Decision 3. It is the other fix `spec/pll.md` names, and it does not
  address this gap.
- **Relax the Lock criterion from ≤ 1 ns to cover the measured worst-case
  static phase offset (≈1.49 ns, or the 1.796 ns actually measured at
  `ff`/125 °C/3.63 V).** Rejected, and not a decision this record is entitled
  to make: CLAUDE.md is explicit that agents do not relax the ratified spec to
  make results pass. If the loop genuinely cannot hold 1 ns at every corner,
  that is a finding about the loop that must be decided on its own evidence —
  Decision 4 routes it rather than absorbing it.
- **Reduce the window's PVT spread instead of re-centring it** (e.g. a
  supply- or temperature-compensated delay reference rather than a raw
  inverter chain). Not chosen *now* — it is the only route to real margin
  (see Consequences), but it is an architectural change to a cell whose
  simplicity is deliberate, and the measured 1.92× spread does fit inside the
  2× band today. Named here so a future record has the option on the table
  rather than having to rediscover it.
- **Leave row 16 unratified and do nothing.** Rejected: #163's cold-start
  `sim/lock-time` grid (22 PASS / 233 FAIL / 15 ERROR of 270) is largely
  attributable to this window, so row 9's ratification is stuck behind row
  16's. "Recorded rather than papered over" was the right answer for one
  revision; it is not a permanent resting state.

## Consequences

- **Row 16's target column changes**, and its status column changes with it:
  the targets become ones the design can be shown to meet, so the row moves
  from "**the target is not met today**" to a target plus a pending
  re-characterisation. Row 16 is not ratified by *this* record — T4/T5 below
  25 MHz remain open, and the sizing change is not yet implemented or
  re-verified — so DR-007 Amendment A1's carve-out stays in force until both
  halves close.
- **The margin is thin: +1.7 % / +2.2 %.** That is the headline risk of
  Decision 2 and it is not hidden. Three named erosions are unquantified:
  extraction (#18 — wire capacitance adds delay that does not scale with
  `kwc`, moving both the absolute window and its spread), device mismatch
  (the campaign runs `sw_stat_global = sw_stat_mismatch = 0`), and the
  driving XOR's own edge rate (the campaign's ideal-step stimulus measures
  0.3–0.9 % *lower* than `sim/lock-detector`'s in-situ probe at the same two
  binding corners). Any one of them can push a 2 % margin negative.
- **If the margin does go negative, geometry has nothing left to offer.**
  The window's PVT spread is 1.928× at W = 8 µm and 1.906× at W = 26 µm — a
  3.25× sizing change buys 1 % of spread. The band is satisfiable *at all*
  only while the spread stays under 2×, so the next decision, if this one
  erodes, is either a wider stated reach for T2′ (a spec decision needing its
  own record) or a lower-spread delay reference (an architectural one). It is
  **not** another round of re-sizing.
- **Verification owed, and it is substantial.** `sim/lock-detector`'s 95-point
  characterisation must be re-taken against the new sizing before T1′–T5 can
  be claimed; `sim/lock-time`'s 270-run cold-start grid should be re-taken
  after that, since its failures are attributed to the old window; the
  `lock_detector` block layout and `layout/tests/test_lock_detector_devices.py`
  encode W = 8 µm and change with the schematic; and #18's extracted-parasitic
  re-take is what decides whether the +1.7 %/+2.2 % margin survives at all.
  All of this is #393's scope, not this record's.
- **Nothing in `sim/` is invalidated by this record as written.** It changes
  no committed evidence and no design file. The implementation that follows
  it is what invalidates `sim/lock-detector`'s current record — which is why
  that implementation is a separate, gated piece of work.
