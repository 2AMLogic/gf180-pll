#!/usr/bin/env bash
# gf180-pll :: supply-sensitivity :: disambiguate a HIGH-plateau `not-locked`
# verdict after the criterion-3 escalation (#384)
#
#   ./lock_disambiguation.sh <record-id> [outdir]
#
# `20260901-155456-46b92f8` section 3b escalated all 3 sampled step/ramp
# corners to the 40.08 us hold and found `ferr_hi` converges at every one
# (the settling-budget artefact #253 asked about) while `lock_hi` stays near
# zero at every one -- classified `not-locked` rather than `resolved` or
# `genuine`. That single word does not say WHY the flag stays down, and #384
# names three candidate mechanisms that route to different fixes:
#
#   1. measurement window   -- lock_hi's p7..p8 average starts before the
#                               loop re-acquires, even though LOCK itself
#                               re-asserts somewhere later in the hold.
#   2. detector window vs.  -- the loop IS phase-settled (in the sense that
#      residual error          matters for `sim/loop-dynamics`) but
#                               `lock_detector`'s phase-error window is
#                               narrower than that residual, structurally,
#                               at this operating point.
#   3. genuine lock-range   -- the loop is not actually phase-settled yet;
#      / settling finding      a `sim/loop-dynamics` (#10) question.
#
# This script does NOT re-simulate -- every column is arithmetic on data the
# escalated run already committed (`sim/README.md` forbids hand-typed
# numbers in a record for exactly the reason they drift from the data):
#
#   - the retained decimated LOCK trace itself
#     (`corners/<record-id>/supply_transient_<corner>_esc.csv`), scanned over
#     the FULL escalated high-plateau hold rather than only the p7..p8
#     averaging window `lock_hi` uses -- this is what rules 1 in or out;
#   - the static REF->FB phase `tb_supply_dyn.sp` already measures at the
#     p7/p8 window edges (`phi07`/`phi08` in the corner's own
#     `dynx_<corner>.log`) -- the record's own Methodology states this is the
#     same quantity as the UP/DN pulse-width skew at `lock_detector`'s own
#     inputs ("w_up - w_dn == the REF->FB skew"), read at a different node;
#   - the SAME corner's STEADY-STATE static phase and LOCK verdict at the
#     same 3.63 V rail, from `corners/<record-id>/supply_steady.csv` -- the
#     control condition: does this detector, at this corner, assert LOCK at
#     all once the phase has actually settled?
#   - `sim/lock-detector`'s own measured assert/deassert window
#     (`window_edges.csv`), the independent characterisation of mechanism 2.
#
# SCHEMA CHANGE (#389), called out here per `sim/README.md` ("a testbench
# change that affects comparability must be called out in the next record"):
# two columns were appended after `steady_lock_ok` --
#
#   ld_assert_ns      the assert edge of this corner's detector window
#                     (`asserted_up_to_s` in window_edges.csv), i.e. the
#                     largest static phase error that still let the detector
#                     assert. Already implicit in `ld_window_ns`'s low end;
#                     emitted numerically so the subtraction below is
#                     auditable without opening window_edges.csv.
#   phase_to_shed_ns  phi08_ns - ld_assert_ns -- how much phase a corner still
#                     has to shed, at the escalated hold's own end, before
#                     LOCK could assert. This is the quantity that ranks the
#                     corners by "distance from settled". It is NOT the
#                     settled value's distance below the window edge, which is
#                     a different (and, for ranking, meaningless) number:
#                     record `20260915-105055-2d6ab99` ranked the corners on
#                     that wrong quantity and stated the comparison inverted
#                     (#389, corrected by the record that supersedes it). The
#                     column exists so the ranking is machine-derived rather
#                     than hand-typed, per this campaign's own standard.
#
#                     Caveat: `phase_to_shed_ns` is a settling-distance metric
#                     only at a corner whose OWN undisturbed steady state
#                     asserts LOCK (`steady_lock_ok=yes`). Where it does not
#                     (`ff`/125 C here), the corner is structurally outside
#                     its detector window even fully settled, so no amount of
#                     shedding reaches assertion and the number ranks nothing.
#
# A CSV emitted before this change has 11 columns and no header comment for
# either; one emitted after has 13. Nothing under `corners/` is rewritten --
# the pre-change CSV stays exactly as committed (`sim/README.md`, append-only).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP="$(cd "${HERE}/.." && pwd)"
ROOT="$(cd "${EXP}/../.." && pwd)"

RID="${1:?usage: lock_disambiguation.sh <record-id> [outdir]}"
OUT="${2:-${EXP}/corners/${RID}}"
SRC="${EXP}/corners/20260901-155456-46b92f8"
[ -d "${SRC}" ] || { echo "ERROR: ${SRC} not found -- this script reads the #253/#255 escalated run" >&2; exit 1; }

LD_WINDOW="${ROOT}/sim/lock-detector/corners/20260802-050119-c24ee3a/window_edges.csv"
[ -f "${LD_WINDOW}" ] || { echo "ERROR: ${LD_WINDOW} not found" >&2; exit 1; }

mkdir -p "${OUT}"

# The 3 sampled step/ramp corners (fixed by run.sh's DYN_PICKS), the escalated
# high-plateau window edges (KD_TA_HI_X/KD_TB_HI_X), and the step-edge instant
# (KD_TSTEP+KD_TEDGE) whose ~100 ns of rail-coupling on the LOCK node is
# excluded from the "does LOCK ever come up on this plateau" scan below --
# it is capacitive coupling to the moving rail (LOCK tracks VDD exactly for
# the duration of the edge, see this record's Methodology), not an assertion.
TB_HI=40.1e-6
EDGE_GUARD=5.9e-6   # step edge (100 ns) + measured coupling settle (see Methodology)

TABLE="${OUT}/lock_disambiguation.csv"
{
  echo "# campaign: supply-sensitivity (#384)"
  echo "# source record (read-only, never modified): ${SRC##*/}"
  echo "# generated_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "# NO SIMULATION WAS RUN. Every column is arithmetic on committed data."
  echo "# high-plateau scan window (excl. step-edge coupling): ${EDGE_GUARD}s .. ${TB_HI}s"
  echo "# window_lo/window_hi_v: min/max |LOCK| over that window, from the retained _esc.csv trace"
  echo "# ld_window_ns: sim/lock-detector's own measured assert/deassert phase-error window at this process/temp (window_edges.csv)"
  echo "# steady_phase_ns / steady_lock_ok: this SAME corner's undisturbed steady-state static phase and LOCK verdict at the SAME 3.63 V rail (supply_steady.csv) -- the control condition"
  echo "# steady_phase_ns is a SIGNED REF->FB skew; the detector window bounds its MAGNITUDE, so compare |steady_phase_ns| against ld_window_ns"
  echo "# ld_assert_ns: assert edge of this corner's detector window (asserted_up_to_s) -- the largest static phase error that still asserted"
  echo "# phase_to_shed_ns: phi08_ns - ld_assert_ns -- phase still to shed at the escalated hold's end before LOCK could assert; ranks the corners by distance from settled. Meaningful only where steady_lock_ok=yes (see this script's header)"
  echo "bundle,temp_c,phi07_ns,phi08_ns,ferr_hi,lock_hi_v,lock_plateau_max_v,lock_plateau_mean_v,ld_window_ns,steady_phase_ns,steady_lock_ok,ld_assert_ns,phase_to_shed_ns"
  for row in "typical 27" "ff 125" "ss -40"; do
    # shellcheck disable=SC2086  # intentional word-splitting of "bundle temp"
    set -- ${row}; bundle="$1"; temp="$2"
    log="${SRC}/dynx_${bundle}_${temp}c_3.30v.log"
    esc="${SRC}/supply_transient_${bundle}_${temp}c_3.30v_esc.csv"
    steady="${SRC}/supply_steady.csv"
    [ -f "${log}" ] || { echo "ERROR: ${log} not found" >&2; exit 1; }
    [ -f "${esc}" ] || { echo "ERROR: ${esc} not found" >&2; exit 1; }
    [ -f "${steady}" ] || { echo "ERROR: ${steady} not found" >&2; exit 1; }

    phi07="$(awk '/^phi07 /{print $3; exit}' "${log}")"
    phi08="$(awk '/^phi08 /{print $3; exit}' "${log}")"
    ferr_hi="$(awk '/^ferr_hi /{print $3; exit}' "${log}")"
    lock_hi="$(awk '/^lock_hi /{print $3; exit}' "${log}")"

    read -r lmax lmean <<<"$(awk -F, -v lo="${EDGE_GUARD}" -v hi="${TB_HI}" '
      !/^#/ && $1 != "t_s" {
        t=$1+0; l=$3+0; if (l<0) l=-l;
        if (t>=lo && t<=hi) { if (l>max) max=l; sum+=l; n++ }
      }
      END { printf "%.6g %.6g", max+0, (n>0?sum/n:0) }' "${esc}")"

    ldwin="$(awk -F, -v b="${bundle}" -v t="${temp}" '
      !/^#/ && $1 != "process" && $1==b && $2==t+0 {
        printf "%.3g-%.3g", $4*1e9, $5*1e9
      }' "${LD_WINDOW}")"

    # Assert edge on its own, and the phase still to shed against it. Derived
    # here rather than in the record's prose: a hand-typed comparative is
    # exactly what drifted from the data in `20260915-105055-2d6ab99` (#389).
    ldassert="$(awk -F, -v b="${bundle}" -v t="${temp}" '
      !/^#/ && $1 != "process" && $1==b && $2==t+0 { printf "%.17g", $4*1e9 }' "${LD_WINDOW}")"
    [ -n "${ldassert}" ] || { echo "ERROR: no window_edges.csv row for ${bundle}/${temp}C" >&2; exit 1; }

    read -r sphase slock <<<"$(awk -F, -v b="${bundle}" -v t="${temp}" '
      !/^#/ && $1 != "bundle" && $1==b && $2==t+0 && ($3+0)==3.63 {
        lockok = ($17+0 >= 0.9*3.63) ? "yes" : "no";
        printf "%.6g %s", $8*1e9, lockok
      }' "${steady}")"

    printf "%s,%s,%.4g,%.4g,%.6g,%.6g,%.6g,%.6g,%s,%.4g,%s,%.4g,%.4g\n" \
      "${bundle}" "${temp}" \
      "$(awk -v v="${phi07}" 'BEGIN{print v*1e9}')" \
      "$(awk -v v="${phi08}" 'BEGIN{print v*1e9}')" \
      "${ferr_hi}" "${lock_hi}" "${lmax}" "${lmean}" "${ldwin}" "${sphase}" "${slock}" \
      "${ldassert}" \
      "$(awk -v p="${phi08}" -v a="${ldassert}" 'BEGIN{print p*1e9 - a}')"
  done
} >"${TABLE}"

echo "lock_disambiguation: wrote ${TABLE}"
cat "${TABLE}"
