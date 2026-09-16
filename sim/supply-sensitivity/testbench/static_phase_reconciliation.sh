#!/usr/bin/env bash
# gf180-pll :: supply-sensitivity :: is the reported `phi_b_s` a SETTLED static
# phase offset, and how many corners clear `spec/pll.md`'s ratified 1 ns Lock
# criterion? (#394)
#
#   ./static_phase_reconciliation.sh <record-id> [outdir]
#
# #394 asks why `20260901-155456-46b92f8` reports 1.796 ns of static REF->FB
# phase at `ff`/125 C/3.63 V when `spec/pll.md`'s static phase-offset budget
# cites 0.671 ns (`sim/pfd-deadzone`) as the systematic worst-corner term, and
# asks whether that corner is a singular outlier.  This script answers the
# arithmetic half of both questions from data already committed; the
# operating-point half (does `pfd-deadzone`'s number move if it is measured at
# the loop's own f_ref and Vctrl?) needs simulation and is
# `sim/pfd-deadzone/testbench-operating-point/`'s.
#
# LIKE ITS THREE PREDECESSORS IN THIS CAMPAIGN (`20260801-114140-f87afc5`,
# `20260915-105055-2d6ab99`, `20260915-124108-49f539f`) THIS SCRIPT
# RE-SIMULATES NOTHING.  Every column is arithmetic on `supply_steady.csv`,
# which `sim/README.md`'s append-only rule keeps byte-identical.
#
# ------------------------------------------------------------------ column 1
# TWO THRESHOLDS, AND THEY ARE NOT THE SAME NUMBER.  This is the first thing
# the table shows and it is not a rounding difference:
#
#   over_ratified   |phi_b| against `spec/pll.md`'s ratified Lock criterion,
#                   an ABSOLUTE 1 ns at the PFD inputs.
#   over_deck       |phi_b| against what `run.sh` actually applied when it
#                   wrote the `verdict` column: `ACC_PHI_FRAC` = 2 % of a
#                   reference period, i.e. 1.6 ns at this campaign's
#                   f_ref = 12.5 MHz (and 3.2 ns at its 6.25 MHz power-split
#                   bundle).
#
# A row can therefore read `PASS` while standing off 1.4 ns -- 40 % past the
# ratified bound.  `over_deck` exists so that gap is visible in the data rather
# than only in this comment.
#
# `run.sh` HAS SINCE BEEN TIGHTENED to the ratified bound (`ACC_PHI_S`, #394),
# so the two columns will agree on any FUTURE run.  They are still both
# reported, and `SRC_ACC_PHI_FRAC` below is still PINNED to 0.02 rather than
# sourced from `run.sh`, because this script reads a FROZEN record that was
# judged at the old threshold: re-reading that record through today's runner
# constants would silently restate its verdicts, which is the opposite of what
# an append-only evidence directory is for.
#
# ------------------------------------------------------------------ column 2
# IS `phi_b` A STATIC OFFSET AT ALL?  `tb_supply_lock.sp` measures the REF->FB
# skew TWICE, at `ta` and at `tb`, and reports
#
#     ferr = -(phi_b - phi_a) / (tb - ta)
#
# because a residual frequency error slips the phase at exactly df/f seconds
# per second.  That identity is invertible: `phi_a` -- the same phase measured
# (tb - ta) earlier -- is recoverable EXACTLY from two committed columns,
#
#     phi_a = phi_b + ferr * (tb - ta),
#
# with no model and no new simulation.  `d_phi_window_ns` is what the "static"
# phase did across that window.  A corner whose phase moved by a large fraction
# of the criterion between the two instants was not measured in steady state,
# and `phi_b` there is a SAMPLE ON A DECAYING TAIL rather than the offset the
# loop stands off.
#
# This matters because of where the window sits.  `run.sh` runs the grid to
# `KTSTOP` = 12.0 us with `KTA` = 6.4 us and `KTB` = 9.6 us, which its own
# header states are 0.69 and 1.03 of the loop's slowest time constant
# (`KTAU` = 9.3 us = 1/(2*pi*R*C1)).  One tau is not settled.  The runner's
# settling escalation to 36.8 us (3.96 tau) exists for exactly this, but it is
# gated on `|ferr| > ACC_FERR` = 1e-3 ONLY -- nothing in the grid gates the
# PHASE on settledness, so a corner can carry a visibly-moving phase to the
# record while passing the frequency gate.
#
# ------------------------------------------------------------------ column 3
# WHERE WOULD IT LAND?  `asymptote_ns` continues the two committed samples with
# the loop's OWN dominant time constant:
#
#     k = exp(-(tb - ta) / KTAU);   a = (phi_b - k * phi_a) / (1 - k)
#
# THIS IS NOT A MEASUREMENT, and it is a far weaker extrapolation than
# `settling_extrapolation.sh`'s: its numerator is a difference of two nearly
# equal numbers, so a small error in either sample moves `a` a lot.  Worse,
# `20260901-155456-46b92f8` section 3c measured this loop's END-plateau
# frequency residual decaying ~16x SLOWER than single-pole at `ss`/-40 C and
# classified it `under-damped`; if the phase tail shares that behaviour the
# column understates the settled value.  It is printed to show the SIGN and
# ORDER of the answer -- "far below `phi_b`", not "equal to this number" -- and
# a corner that needs a real number needs `run.sh`'s settling escalation run at
# it, which is what this record's simulated half does.
#
# --------------------------------------------------------- what comes out of
# THE ANSWER IS AN INTERSECTION, NOT A COUNT.  "17 of 45 rows exceed 1 ns"
# sounds like a verdict and is not one: 15 of those 17 were still moving when
# `phi_b` was sampled, and every one of them was moving DOWNWARD, so at those
# corners the committed number is an upper bound on a decaying tail.  The rows
# that actually say something about the ratified criterion are the ones that
# are over the bound AND settled -- there the record's own two instants agree
# the phase has stopped moving and it is still outside the bound.  The summary
# block at the bottom prints that intersection explicitly, because a reader who
# stops at the first line will draw the wrong conclusion in whichever direction
# they were already leaning.
#
# ------------------------------------------------------------------ column 4
# THE INDEPENDENT CROSS-CHECK.  `tb_supply_lock.sp` measures the same static
# offset a second way, as the UP/DN pulse-WIDTH difference at the PFD outputs
# (`skew_s`), from different nodes, different edges and different `.meas`
# cards; its own header states that a disagreement between the two is a
# measurement error rather than a design result.  `xcheck_pct` prints the
# disagreement so no conclusion below rests on an unverified `phi_b`.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP="$(cd "${HERE}/.." && pwd)"

RID="${1:?usage: static_phase_reconciliation.sh <record-id> [outdir]}"
OUT="${2:-${EXP}/corners/${RID}}"
SRC="${EXP}/corners/20260901-155456-46b92f8"
STEADY="${SRC}/supply_steady.csv"
[ -f "${STEADY}" ] || {
  echo "ERROR: ${STEADY} not found -- this script reads the 45-point steady-state grid" >&2
  exit 1
}

mkdir -p "${OUT}"

# The ratified criterion, from `spec/pll.md` "Lock criterion".  An ABSOLUTE
# bound on the static phase error at the PFD inputs, independent of f_ref.
ACC_PHI_RATIFIED_S=1e-9

# What `run.sh` applied when it wrote the `verdict` column of the source CSV,
# restated here rather than sourced: `run.sh` is a mutable testbench and this
# script reads a FROZEN record, so the threshold that record was judged at has
# to be pinned to the record, not to whatever the runner says today.  If the
# two ever diverge the divergence is the finding, and hiding it behind a
# `source` would erase it.
SRC_ACC_PHI_FRAC=0.02
SRC_FREF=12.5e6

# `run.sh`'s late-window instants and the loop's own time constant, as of the
# source record (`KTA`/`KTB`/`KTAU`; every row of that CSV carries
# `tstop = 12.0u`, the unescalated default, which is what makes these the right
# constants for it).  Pinned for the same reason as the threshold above.
SRC_TSTOP=12.0u
SRC_TA=6.4e-6
SRC_TB=9.6e-6
SRC_TAU=9.3e-6

TABLE="${OUT}/static_phase_widened.csv"
{
  echo "# campaign: supply-sensitivity (#394)"
  echo "# source record (read-only, never modified): ${SRC##*/}"
  echo "# generated_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "# NO SIMULATION WAS RUN. Every column is arithmetic on committed data."
  echo "# ratified criterion: |static phase at the PFD inputs| <= 1 ns (spec/pll.md, Lock criterion)"
  echo "# deck criterion actually applied to the source record's verdict column:"
  echo "#   ACC_PHI_FRAC = ${SRC_ACC_PHI_FRAC} of a reference period = $(awk -v p="${SRC_ACC_PHI_FRAC}" -v f="${SRC_FREF}" 'BEGIN{printf "%.4g", p/f*1e9}') ns at f_ref = ${SRC_FREF} Hz"
  echo "# late window: ta=${SRC_TA}s tb=${SRC_TB}s (tstop=${SRC_TSTOP}); loop tau=${SRC_TAU}s"
  echo "#   -> ta/tb are $(awk -v a="${SRC_TA}" -v t="${SRC_TAU}" 'BEGIN{printf "%.2f", a/t}') and $(awk -v b="${SRC_TB}" -v t="${SRC_TAU}" 'BEGIN{printf "%.2f", b/t}') tau: ONE tau is not settled"
  echo "# phi_b_ns: the committed static REF->FB phase at tb (supply_steady.csv phi_b_s)"
  echo "# skew_ns:  the same offset read as the UP/DN pulse-width difference at the PFD outputs"
  echo "# xcheck_pct: |phi_b - skew| / |phi_b| * 100 -- the two-node cross-check; large = measurement error, not a design result"
  echo "# vctrl_avg_v: the control voltage this closed-loop row settled at. Carried"
  echo "#   because it is the JOIN KEY against sim/pfd-deadzone's open-loop t_offset:"
  echo "#   that campaign's cited 0.671 ns systematic term is measured at ONE control"
  echo "#   voltage (1.65 V), and a closed-loop row standing at a different one is not"
  echo "#   being compared against its own operating point until the two are matched."
  echo "# phi_a_ns: the SAME phase (tb-ta) earlier, recovered exactly from ferr's own definition: phi_a = phi_b + ferr*(tb-ta)"
  echo "# d_phi_window_ns: phi_b - phi_a, how far the 'static' phase moved across the late window"
  echo "# settled: 'no' when |d_phi_window| > 10% of the ratified 1 ns criterion -- i.e. the"
  echo "#   phase moved by more than a tenth of the bound it is being judged against, between"
  echo "#   the record's own two measurement instants, so phi_b is a sample on a tail"
  echo "# asymptote_ns: single-pole continuation to t->inf at the loop's own tau. NOT A"
  echo "#   MEASUREMENT: two-point fit, numerator is a difference of near-equal numbers, and"
  echo "#   this loop is measured under-damped at one corner. Read its SIGN and ORDER only."
  echo "# over_ratified: |phi_b| > 1 ns (the ratified criterion)"
  echo "# over_deck: |phi_b| > the deck threshold above (what the verdict column applied)"
  echo "# verdict: the source record's own verdict, unchanged"
  echo "bundle,temp_c,vdd_v,phi_b_ns,skew_ns,xcheck_pct,vctrl_avg_v,ferr,phi_a_ns,d_phi_window_ns,settled,asymptote_ns,over_ratified,over_deck,verdict"
  awk -F, -v OFS=, \
      -v accr="${ACC_PHI_RATIFIED_S}" -v accp="${SRC_ACC_PHI_FRAC}" -v fref="${SRC_FREF}" \
      -v ta="${SRC_TA}" -v tb="${SRC_TB}" -v tau="${SRC_TAU}" -v dflt_ts="${SRC_TSTOP}" '
    function abs(x) { return x < 0 ? -x : x }
    /^#/ { next }
    $1 == "bundle" { next }
    NF < 22 { next }
    {
      bundle=$1; temp=$2; vdd=$3+0;
      ferr=$7+0; phib=$8+0; skew=$9+0; vctrl=$15+0; verdict=$22; ts=$23;

      # The phi_a reconstruction is only valid at the window this script is
      # pinned to. A row run at a non-default transient length carries a
      # DIFFERENT (tb - ta), which the CSV does not record -- so those columns
      # are left empty rather than computed against the wrong interval.
      same_window = (ts == dflt_ts);

      dt = tb - ta;
      phia = same_window ? phib + ferr * dt : "";
      dphi = same_window ? phib - phia : "";

      # A phase still moving by more than a tenth of the criterion, between the
      # record'"'"'s own two instants, is not a settled static offset.
      settled = same_window ? ((abs(dphi) > 0.10 * accr) ? "no" : "yes") : "";

      k = exp(-dt / tau);
      asym = (same_window && (1 - k) != 0) ? (phib - k * phia) / (1 - k) : "";

      xchk = (phib != 0) ? abs(phib - skew) / abs(phib) * 100 : "";

      overr = (abs(phib) > accr) ? "yes" : "no";
      overd = (abs(phib) > accp / fref) ? "yes" : "no";

      printf "%s,%s,%.2f,%.4g,%.4g,%s,%.4g,%.4g,%s,%s,%s,%s,%s,%s,%s\n",
        bundle, temp, vdd, phib * 1e9, skew * 1e9,
        (xchk == "" ? "" : sprintf("%.3g", xchk)), vctrl, ferr,
        (phia == "" ? "" : sprintf("%.4g", phia * 1e9)),
        (dphi == "" ? "" : sprintf("%.4g", dphi * 1e9)),
        settled,
        (asym == "" ? "" : sprintf("%.4g", asym * 1e9)),
        overr, overd, verdict;
    }' "${STEADY}"
} >"${TABLE}"

echo "static_phase_reconciliation: wrote ${TABLE}"

# ---------------------------------------------------------------------------
# The counts #394 asks for, derived from the table rather than restated in
# prose -- the same standard #389 imposed on this campaign after a hand-typed
# comparative drifted from its own data.
#
# THE LOAD-BEARING LINE IS THE LAST ONE, not the first.  "over the ratified
# criterion" counts rows whose committed `phi_b` exceeds 1 ns; most of those
# rows were still moving when `phi_b` was sampled, so they are UPPER BOUNDS on
# a decaying tail and do not by themselves indict anything.  The rows that do
# indict the criterion are the ones that are over the bound AND settled: at
# those, the grid's own two measurement instants agree that the phase has
# stopped moving and is still outside the bound.  That intersection is the
# only population from which "the loop does not meet the criterion here" can
# be read off this record.
# ---------------------------------------------------------------------------
SUMMARY="${OUT}/static_phase_widened_summary.txt"
awk -F, -v accr="${ACC_PHI_RATIFIED_S}" '
  function abs(x) { return x < 0 ? -x : x }
  /^#/ { next }
  $1 == "bundle" { next }
  { n++;
    over = ($13 == "yes"); settled = ($11 == "yes");
    if (over)                   nr++;
    if ($14 == "yes")           nd++;
    if (!settled)               nu++;
    if (over && $14 == "no")    gap++;
    if (over && !settled)       ru++;
    # An overall PASS verdict on a row standing off more phase than the
    # ratified criterion allows: the gap between what the deck asserted and
    # what the spec requires, counted rather than described.
    if (over && $15 == "PASS")  np++;
    # The source record classified its `FAIL:lock` rows as a lock-detector
    # window question routed to #11, "not a loop failure". That reading is
    # only available if those rows are INSIDE the ratified phase criterion --
    # a part standing off more phase than the criterion allows is not locked,
    # so a flag refusing to assert there is correct rather than defective.
    # Counted, not assumed, in both directions.
    if ($15 == "FAIL:lock") { nl++; if (over) nlo++; }
    if (over && settled) {
      ns++;
      id = $1 "/" $2 "C/" $3 "V";
      list = list sprintf("\n    %-22s phi_b = %6.4g ns  d_phi = %8.4g ns  xcheck = %5s %%  verdict = %s",
                          id, $4, $10, $6, $15);
      if (abs($4) > worst) { worst = abs($4); worst_id = id }
    }
  }
  END {
    printf "rows                                              : %d\n", n;
    printf "over the ratified %.3g ns Lock criterion            : %d\n", accr * 1e9, nr;
    printf "over the deck threshold the verdict applied       : %d\n", nd;
    printf "over ratified but under the deck threshold        : %d\n", gap;
    printf "over ratified yet carrying an overall PASS        : %d\n", np + 0;
    printf "phase still moving across the late window         : %d\n", nu;
    printf "  ... of the over-ratified rows                   : %d of %d\n", ru, nr;
    printf "rows whose own LOCK flag did not assert           : %d\n", nl + 0;
    printf "  ... of those, also over the ratified criterion  : %d of %d\n", nlo + 0, nl + 0;
    printf "OVER THE RATIFIED CRITERION *AND* SETTLED         : %d%s\n",
           ns + 0, (ns ? list : "  (none)");
    if (ns) printf "\n  worst settled violation                         : %.4g ns at %s\n",
                   worst, worst_id;
  }' "${TABLE}" | tee "${SUMMARY}"

echo "static_phase_reconciliation: wrote ${SUMMARY}"
