#!/usr/bin/env bash
# gf180-pll :: supply-sensitivity :: how much longer the post-step phase tail
# had to run before `lock` could re-assert (#387, finding 2)
#
#   ./settling_extrapolation.sh <record-id> [outdir]
#
# `20260915-124108-49f539f` (superseding `20260915-105055-2d6ab99` on its
# ranking only) classified `ss`/-40 C and `typical`/27 C's HIGH-plateau
# `not-locked` verdict as (3) -- a transient phase-settling tail, not a
# structural detector-window mismatch -- and quantified the distance from
# settled as `phase_to_shed_ns`, the phase each corner still had to shed at
# the escalated 40.08 us hold's own end before `lock_detector` could assert.
#
# It did NOT say how much longer that would take.  That is the question #387
# asks of the loop filter, and it is the only new arithmetic here.  Like its
# two predecessors in this campaign (`20260801-114140-f87afc5`,
# `20260915-105055-2d6ab99`) this script RE-SIMULATES NOTHING: every column is
# arithmetic on data already committed under `20260901-155456-46b92f8` and
# `sim/lock-detector/corners/20260802-050119-c24ee3a`.
#
# TWO extrapolations, deliberately BOTH reported, because neither is a
# measurement and the decision record that cites this file must quote a
# bracket rather than a number:
#
#   t_extra_linear_us       the remaining phase divided by the mean decay rate
#                           actually measured across the p7..p8 window.  A
#                           decaying response slows as it converges, so a
#                           straight-line continuation of the CURRENT rate is
#                           the OPTIMISTIC end of the bracket.
#
#   t_extra_singlepole_us   the same distance closed by a single exponential
#                           with the loop's OWN dominant closed-loop time
#                           constant -- tau = 1/(2 pi f_p) with f_p = 17.09 kHz
#                           = 1/(2 pi R C1), the pole `spec/pll.md`'s Lock time
#                           section names as the structural settling floor and
#                           the same KTAU `run.sh`'s settling escalations are
#                           built on.  The asymptote is not assumed: it is
#                           SOLVED for from the two committed samples and that
#                           tau (implied_asymptote_ns below), so the column is
#                           a two-parameter fit to two points, with all the
#                           fragility that implies.
#
# WHY NEITHER IS A MEASUREMENT, stated here and not only in the record so a
# reader of the CSV cannot take the last column for a result:
# `20260901-155456-46b92f8` section 3c measured the END-plateau frequency
# residual at this SAME `ss`/-40 C corner decaying by a factor 0.809 over
# 3 tau against a 0.0493 single-pole expectation -- roughly 16x slower than
# single-pole -- and classified it `under-damped` on that basis.  If the
# post-step PHASE tail shares that behaviour, both columns below understate
# the real re-lock time by a large factor.  The columns bracket what the
# committed data can support; they do not settle it.  A campaign that measures
# it (a longer hold, run to `lock` re-assertion, or per-cycle phase
# instrumentation) is named as verification owed by the decision record this
# file backs.
#
# The model-free column is `ratio_to_assert_meas`: (phi08 - a)/(phi07 - a),
# the observed shrink factor of the distance-to-assert-edge across one p7..p8
# window, with no asymptote assumed at all.  Compare it against
# `k_singlepole` = exp(-dt/tau), what one pole at the loop's own tau would
# give over the same interval.  Below k_singlepole means the distance to the
# assert edge was closing FASTER than one pole over the window observed.
#
# Reads, and never modifies:
#   corners/20260901-155456-46b92f8/dynx_<corner>_3.30v.log
#       phi07/phi08 and their own TRIG instants (the measurement times, so dt
#       is read rather than assumed), and t_step/t_edge (the step-edge end,
#       which is where every "from the step edge" time below is measured from)
#   corners/20260901-155456-46b92f8/supply_steady.csv
#       the same corner's undisturbed steady-state LOCK verdict at 3.63 V --
#       the gate on whether a settling extrapolation means anything at all at
#       this corner (it does not at `ff`/125 C, which is structural)
#   sim/lock-detector/corners/20260802-050119-c24ee3a/window_edges.csv
#       the assert edge the phase has to get back inside

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP="$(cd "${HERE}/.." && pwd)"
ROOT="$(cd "${EXP}/../.." && pwd)"

RID="${1:?usage: settling_extrapolation.sh <record-id> [outdir]}"
OUT="${2:-${EXP}/corners/${RID}}"
SRC="${EXP}/corners/20260901-155456-46b92f8"
[ -d "${SRC}" ] || { echo "ERROR: ${SRC} not found -- this script reads the #253/#255 escalated run" >&2; exit 1; }

LD_WINDOW="${ROOT}/sim/lock-detector/corners/20260802-050119-c24ee3a/window_edges.csv"
[ -f "${LD_WINDOW}" ] || { echo "ERROR: ${LD_WINDOW} not found" >&2; exit 1; }

mkdir -p "${OUT}"

# The loop's dominant closed-loop pole, as a FREQUENCY, exactly as
# spec/pll.md's Lock time section states it ("the slowest closed-loop pole
# sits near 1/(2 pi R C1) = 17.09 kHz").  tau is derived from it below rather
# than typed in, so this script carries one cited number and not two.
FP_HZ=17.09e3

TABLE="${OUT}/settling_extrapolation.csv"
{
  echo "# campaign: supply-sensitivity (#387, finding 2)"
  echo "# source record (read-only, never modified): ${SRC##*/}"
  echo "# ranking/derivation predecessor: 20260915-124108-49f539f (which supersedes 20260915-105055-2d6ab99 on its ranking only)"
  echo "# generated_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "# NO SIMULATION WAS RUN. Every column is arithmetic on committed data."
  echo "# dominant closed-loop pole f_p = ${FP_HZ} Hz (spec/pll.md 'Lock time': 1/(2 pi R C1) = 17.09 kHz); tau_s = 1/(2 pi f_p)"
  echo "# t7_s/t8_s: the REF-edge instants phi07/phi08 were actually measured at (the .meas TRIG times), so dt_s is read, not assumed"
  echo "# ld_assert_ns / phase_to_shed_ns: as in lock_disambiguation.csv -- the detector's assert edge, and phi08 minus it"
  echo "# steady_lock_ok: does THIS corner's own undisturbed steady state at the SAME 3.63 V rail assert LOCK? Where this is 'no' the corner is structural (spec row 16), and every extrapolation column below is meaningless for it and is emitted as 'n/a'"
  echo "# ratio_to_assert_meas: (phi08-a)/(phi07-a), model-free shrink factor of the distance to the assert edge over one p7..p8 window"
  echo "# k_singlepole: exp(-dt/tau) -- what one pole at the loop's own tau gives over the same interval. ratio_to_assert_meas BELOW this means the distance was closing faster than one pole over the window observed"
  echo "# implied_asymptote_ns: the settled phase SOLVED for from the two samples and tau -- a two-parameter fit to two points; fragile by construction"
  echo "# t_extra_linear_us: OPTIMISTIC bracket end -- phase_to_shed at the measured mean rate, straight-line"
  echo "# t_extra_singlepole_us: the same distance closed by one pole at tau from the implied asymptote"
  echo "# t_relock_*_us: the corresponding instant measured from the END of the supply step edge (t_step + t_edge), i.e. directly comparable to the 34.4 us the escalated hold actually ran"
  echo "# NEITHER extrapolation is a measurement. 46b92f8 section 3c measured this same ss/-40C corner's END-plateau frequency residual decaying ~16x slower than single-pole ('under-damped'); if the phase tail does the same, both columns understate the answer. See this script's header."
  echo "bundle,temp_c,t7_s,t8_s,dt_s,phi07_ns,phi08_ns,rate_ns_per_us,ld_assert_ns,phase_to_shed_ns,steady_lock_ok,tau_s,k_singlepole,ratio_to_assert_meas,implied_asymptote_ns,t_extra_linear_us,t_extra_singlepole_us,t_edge_end_s,t_relock_linear_us,t_relock_singlepole_us"
  for row in "typical 27" "ff 125" "ss -40"; do
    # shellcheck disable=SC2086  # intentional word-splitting of "bundle temp"
    set -- ${row}; bundle="$1"; temp="$2"
    log="${SRC}/dynx_${bundle}_${temp}c_3.30v.log"
    steady="${SRC}/supply_steady.csv"
    [ -f "${log}" ] || { echo "ERROR: ${log} not found" >&2; exit 1; }
    [ -f "${steady}" ] || { echo "ERROR: ${steady} not found" >&2; exit 1; }

    # phi07/phi08 and, from the same .meas lines, the REF-edge instants they
    # were taken at ("trig=" field) -- so the sample spacing is read off the
    # committed log rather than assumed to equal p8-p7.
    read -r phi07 t7 <<<"$(awk '/^phi07 /{for(i=1;i<=NF;i++) if($i=="trig=") tg=$(i+1); print $3, tg; exit}' "${log}")"
    read -r phi08 t8 <<<"$(awk '/^phi08 /{for(i=1;i<=NF;i++) if($i=="trig=") tg=$(i+1); print $3, tg; exit}' "${log}")"
    [ -n "${t7}" ] && [ -n "${t8}" ] || { echo "ERROR: could not read phi07/phi08 TRIG instants from ${log}" >&2; exit 1; }

    t_step="$(awk -F= '/^\.param t_step=/{print $2; exit}' "${log}")"
    t_edge="$(awk -F= '/^\.param t_edge=/{print $2; exit}' "${log}")"
    [ -n "${t_step}" ] && [ -n "${t_edge}" ] || { echo "ERROR: could not read t_step/t_edge from ${log}" >&2; exit 1; }

    ldassert="$(awk -F, -v b="${bundle}" -v t="${temp}" '
      !/^#/ && $1 != "process" && $1==b && $2==t+0 { printf "%.17g", $4*1e9 }' "${LD_WINDOW}")"
    [ -n "${ldassert}" ] || { echo "ERROR: no window_edges.csv row for ${bundle}/${temp}C" >&2; exit 1; }

    slock="$(awk -F, -v b="${bundle}" -v t="${temp}" '
      !/^#/ && $1 != "bundle" && $1==b && $2==t+0 && ($3+0)==3.63 {
        print ($17+0 >= 0.9*3.63) ? "yes" : "no"
      }' "${steady}")"
    [ -n "${slock}" ] || { echo "ERROR: no supply_steady.csv row for ${bundle}/${temp}C at 3.63 V" >&2; exit 1; }

    awk -v b="${bundle}" -v temp="${temp}" -v p7="${phi07}" -v p8="${phi08}" \
        -v t7="${t7}" -v t8="${t8}" -v a="${ldassert}" -v slock="${slock}" \
        -v fp="${FP_HZ}" -v tstep="${t_step}" -v tedge="${t_edge}" '
      function sec(v,  n,s) {
        # SPICE suffix -> seconds, for the .param values read off the deck.
        s = v; sub(/[a-zA-Z]+$/, "", s); n = s + 0;
        if (v ~ /[uU]$/) return n*1e-6;
        if (v ~ /[nN]$/) return n*1e-9;
        if (v ~ /[pP]$/) return n*1e-12;
        if (v ~ /[mM]$/) return n*1e-3;
        return n;
      }
      BEGIN {
        pi = atan2(0, -1);
        tau = 1.0/(2*pi*fp);
        p7ns = p7*1e9; p8ns = p8*1e9;
        dt = t8 - t7;
        dtus = dt*1e6;
        rate = (p7ns - p8ns)/dtus;          # ns per us, mean over the window
        shed = p8ns - a;
        k = exp(-dtus/(tau*1e6));
        edge_end = sec(tstep) + sec(tedge);
        t8_from_edge = (t8 - edge_end)*1e6;

        if (slock != "yes") {
          printf "%s,%s,%.6g,%.6g,%.6g,%.4g,%.4g,%.4g,%.4g,%.4g,%s,%.6g,%.6g,n/a,n/a,n/a,n/a,%.6g,n/a,n/a\n",
                 b, temp, t7, t8, dt, p7ns, p8ns, rate, a, shed, slock, tau, k, edge_end;
          exit;
        }

        ratio = (p8ns - a)/(p7ns - a);
        # Single pole through two samples: x(t) = A + B exp(-t/tau) gives
        #   A = (x8 - k x7)/(1 - k),   k = exp(-dt/tau)
        A = (p8ns - k*p7ns)/(1 - k);
        tlin = shed/rate;
        if ((p8ns - A) > 0 && (a - A) > 0)
          tsp = (tau*1e6) * log((p8ns - A)/(a - A));
        else
          tsp = -1;

        printf "%s,%s,%.6g,%.6g,%.6g,%.4g,%.4g,%.4g,%.4g,%.4g,%s,%.6g,%.6g,%.4g,%.4g,%.4g,%.4g,%.6g,%.4g,%.4g\n",
               b, temp, t7, t8, dt, p7ns, p8ns, rate, a, shed, slock, tau, k,
               ratio, A, tlin, tsp, edge_end,
               t8_from_edge + tlin, t8_from_edge + tsp;
      }'
  done
} >"${TABLE}"

echo "settling_extrapolation: wrote ${TABLE}"
cat "${TABLE}"
