# DR-005: a bias buffer on the charge pump's dump node is not "an opamp in the loop path"

- **Status**: proposed (this is a scope reading of DR-001 Decision 1, not a
  change to it; it becomes binding on the same governance path as DR-001, #1)
- **Date**: 2026-07-31
- **Decided by**: Builder agent, issue #24
- **Related**: DR-001 Decision 1 (the constraint being interpreted), #9 /
  PR #26 (the design and the before-picture evidence), #24 (this work), #10
  (loop filter / spur analysis — the consumer of the control-node loading
  argued below), #14 (supply sensitivity), #15 (Monte Carlo mismatch)

## Context

DR-001 Decision 1 ratifies a **passive** second-order loop filter and states
the constraint as: *"No active filter, no opamp in the loop path."* Its
"Alternatives considered" section rejects an **active (opamp-based) loop
filter** on four specific grounds: (a) Vctrl headroom is ample at 3.3 V so the
level-shifting an active filter buys is not needed; (b) an opamp costs static
current against a 5 mW budget; (c) it adds 1/f noise **directly onto the
control node**, the most jitter-sensitive node in the block; and (d) it adds a
second stability problem nested inside the PLL loop.

#9's characterization then found that the charge pump's dominant static-phase
error is **not** current mismatch but the **tail-node charge exchange**: when a
steering switch closes, the tail node it was parked on is dragged from the dump
node's voltage to the control-node voltage, and that charge comes out of the
control node once per reference cycle. The residue is proportional to
`(V_dump − Vctrl)`, so with `V_dump` fixed it nulls at exactly one control
voltage and grows linearly away from it — measured at **−19.4 ns … +15.8 ns**
of effective UP/DN pulse-width skew across the 0.9–2.4 V window
(`sim/cp-compliance/corners/20260731-122451-63e4b47/cp_switch.csv`), i.e. most
of a reference period at the 25 MHz top of the ratified range.

#9 declined the textbook fix — a unity-gain buffer holding the dump node at the
control-node voltage — and named DR-001 Decision 1 as the reason, while
explicitly flagging that the buffer is *arguably* a bias helper rather than a
loop-filter element and that the question needed a record. #24 makes that
question binding, because the mitigation it asks for is precisely that buffer.

## Decision

**DR-001 Decision 1's "no opamp in the loop path" constraint governs elements
that carry the loop's signal charge or shape its transfer function. It does not
prohibit an amplifier whose only job is to hold an internal bias node at a
voltage derived from the control node, provided it satisfies all four
conditions below.** A dump-node tracking buffer meeting them is ratified as
compatible with DR-001 Decision 1, and `design/cp_dumpbuf.sch` is such an
element.

The four conditions, each tied to one of DR-001's own stated objections:

1. **Not in the signal path.** The element must have **no DC or AC current path
   to the control node** — its only connection to that node is a MOS *gate*.
   The loop filter stays exactly the passive series R + C1 / shunt C2 DR-001
   ratified; nothing about the loop transfer function `ω_c ≈ Icp·Kvco·R/(2π·N)`
   changes. (`cp_dumpbuf`: two gates, `MN1` and `MP1`, and nothing else.)
2. **Control-node loading is bounded and declared.** The added capacitance on
   the control node must be **≤ 1 %** of the smallest loop-filter C1 the
   ratified operating space uses, and must be stated in `design/README.md`.
   (`cp_dumpbuf`: 64 µm² of gate area, ≈0.3 pF, against C1 in the ~130 pF range
   from DR-001's sizing check — about 0.2 %.)
3. **Static current is declared and inside budget.** (`cp_dumpbuf`: two 8 µA
   tails, ≈16 µA, ≈53 µW against a 5 mW budget / 2 mW stretch — ≈1 % and
   ≈2.6 % respectively.)
4. **No nested stability problem.** The element must be **single-stage** — one
   high-impedance node, unity-gain feedback, no compensation capacitor and no
   frequency-dependent element the loop's phase margin could interact with; and
   its settling must be fast against the reference period rather than against
   the PLL's loop bandwidth. (`cp_dumpbuf`: two 5-transistor OTAs, each with a
   single dominant pole at its own output, in unity-gain feedback. Verified by
   the campaign re-runs rather than asserted.)

An element failing **any** of the four is an opamp in the loop path for
DR-001's purposes and needs its own record.

## Alternatives considered

- **Read DR-001 Decision 1 literally — no amplifier anywhere in the block.**
  Rejected. The constraint's own rationale is four specific costs (headroom,
  static current, control-node noise, nested stability), every one of which is
  a property of *where* the amplifier sits, not of the word "opamp". Reading it
  as a blanket ban would also forbid the constant-gm bias amplifier the VCO
  already ships in `vco_bias.sch` under DR-001 Decision 2, which no one
  intended. A rule whose literal reading contradicts an already-ratified
  sibling decision is being read wrong.
- **Re-centre the fixed clamp instead, and file no record** (#24's cheap
  option). Rejected on measurement, not on principle: the clamp already parks
  the dump node at **1.487 V**, which is near the centre of the 0.9–2.4 V
  window, so the skew already nulls near mid-window. Re-centring to exactly
  1.65 V improves the worst case by only ≈20 % (−13.9 ns → ≈−10.9 ns at the
  nominal corner) **and makes the 0.9 V end worse** (+8.0 ns → ≈+10.9 ns). The
  cheap option is nearly exhausted; it re-balances the error instead of
  removing it. Kept on the record because the number is the argument.
- **Widen the loop's tolerance for the offset instead (relax the budget).**
  Rejected: CLAUDE.md forbids relaxing a ratified spec to make a result pass,
  and the static offset is a reference-spur mechanism that #10 and #14 consume,
  not a cosmetic number.
- **Two separate dump nodes at fixed voltages either side of the window, so the
  N-side and P-side charge errors cancel.** Rejected on algebra: cancellation
  requires `(C_p + C_n)·Vctrl = C_p·V_dp + C_n·V_dn`, which can only hold at
  one control voltage — the same defect as one fixed node, at twice the device
  count.
- **A source-follower or complementary "diamond" follower instead of an
  amplifier** (no feedback, hence trivially outside any reading of the
  constraint). Rejected on headroom: a follower's output is offset from its
  input by a `V_gs`, and the level-shift stage needed to cancel it must sit at
  `Vctrl ± V_gs` — which at the 2.4 V top of the window on a 2.97 V rail is
  above the supply. There is no room on this rail for a follower-based tracker.
- **Shrink the tail capacitance instead of the voltage step.** Rejected as
  insufficient rather than wrong: the total tail capacitance implied by the
  measured −14.4 ns/V slope at the nominal trim code is ≈73 fF, dominated by
  four legs' cascode drains plus the steering switches, and the switch widths
  are already pinned from below by the turn-on recovery time that sets the
  PFD's minimum pulse (`design/README.md`, PFD section). Any achievable
  reduction is a factor, not a null.

## Consequences

**What this makes possible**

- The dominant term in the charge pump's mismatch budget is removed rather than
  re-balanced. Post-mitigation, the effective UP/DN skew over the whole Vctrl
  window falls from **−19.4 … +15.8 ns** to a fraction of a nanosecond (see the
  `cp-compliance` and `pfd-deadzone` records minted by #24 for the corner-swept
  numbers, and `design/README.md` for the updated budget).
- #10's loop-filter and spur analysis and #12's closed-loop work no longer have
  to treat the static phase offset as strongly Vctrl-dependent.

**What this makes harder, and what we are accepting**

- **Static current the block did not have before** (≈16 µA). It is small, but
  DR-001's objection (b) was real and this is a genuine, permanent cost.
- **Two gates now sit on the control node.** Objection (c) — noise on the most
  jitter-sensitive node — is *reduced*, not eliminated, by the no-current-path
  condition: while the buffer's own source nodes slew, their `C_gs` exchanges
  charge with the control node. That exchange is an offset (its magnitude is
  set by the node excursion, not by the pulse width), and it is **inside** the
  measured charge in both re-run campaigns rather than argued away. The
  buffer's thermal/flicker noise contribution to control-node ripple is **not**
  separately characterized by #24 and is handed to **#14** as a named input:
  a supply/noise record taken after this change must state that it is measuring
  the buffered revision.
- **The clamp is gone, not supplemented.** `MCLPN1/2` / `MCLPP1/2` are removed:
  a diode stack parked at mid-supply would conduct hard against a dump node
  driven to either end of the window. There is therefore no passive fallback if
  the buffer's bias fails — the dump node's definition now depends on
  `IBN`/`IBP` being alive. Bias-generator design (a separate block, out of
  scope here) inherits that as a start-up requirement.
- **Layout**: `MP1`/`MP2` have their bulk tied to their common source, so the
  buffer's PMOS input pair needs its own n-well. #17's floorplan should treat
  `VDUMP`, `NSRC`/`PSRC` and the input pair as matching-critical, and should
  track the post-#24 design rather than the clamped one.
- **This record is a reading of DR-001, so it moves with it.** If DR-001
  Decision 1 is ever superseded (its own "fallback trigger" language
  contemplates that), this record must be re-checked against the replacement
  rather than carried forward silently.
