#!/usr/bin/env bash
# gf180-pll :: supply-sensitivity :: MEASURE the post-supply-step re-lock time
# (#395, DR-011 Decision 4)
#
#   ./relock_measurement.sh <record-id> [outdir]
#
# `settling_extrapolation.sh` (#387, record `20260915-202323-62391c6`) answered
# "how much longer would the post-step phase tail have taken" by extrapolating
# from the only two phase samples the escalated run committed, and its own
# header says in as many words that neither bracket end is a measurement.
# DR-011 Decision 2 declined to promote that bracket to a `spec/pll.md` bound
# for exactly that reason, and Decision 4 named the campaign that would replace
# it.  This script is that campaign's analysis.
#
# WHAT IS DIFFERENT, and it is the whole point: this script reads a
# **per-REFERENCE-CYCLE phase trace** produced by a step/ramp run whose
# high-plateau hold was pushed out **past `lock` re-assertion** rather than
# past `ferr_hi`'s convergence.  Nothing below is extrapolated.  Every time
# reported is an instant the simulation actually reached, and the decay law is
# measured from ~800 samples rather than fitted to 2.
#
# Reads, and never modifies:
#   corners/<record-id>/supply_phase_<corner>_relock.csv
#       the per-REF-cycle REF->FB phase trace (t_ref_s, phi_ns, lock_v,
#       vctrl_v, vdd_v), written by run.sh --one-dyn (#395)
#   corners/<record-id>/dynrl_<corner>.log
#       the same run's generated deck + ngspice output: the profile instants
#       (t_step/t_edge/t_ramp) every "from the step edge" time below is
#       measured against, and `phi07`/`phi08` -- which are NOT used as a
#       result here, only as the free self-check that the trace extraction is
#       right (they sit at instants the trace also covers, so they must agree)
#   sim/lock-detector/corners/20260802-050119-c24ee3a/window_edges.csv
#       the detector's own assert edge, the threshold the phase has to get
#       back inside before `lock` CAN assert
#   corners/20260901-155456-46b92f8/supply_steady.csv
#       the same corner's undisturbed steady-state LOCK verdict at the same
#       3.63 V rail -- the control condition, unchanged in role from
#       settling_extrapolation.sh: where it is `no` the corner is structural
#       (spec row 16 / #393) and no amount of settling time changes its flag
#
# THREE re-lock times are reported per corner, because there are three
# different thresholds in play and conflating them is how a settling result
# turns into a spec claim it cannot support:
#
#   t_relock_assert_us   against `lock_detector`'s OWN measured assert edge --
#                        when the phase re-enters the window the detector can
#                        assert on.  This is the quantity the DR-011 bracket
#                        estimated (37.2 .. 42.6 us).
#   t_relock_1ns_us      against the RATIFIED Lock criterion's phase bound
#                        (<= 1 ns static phase error, spec/pll.md "Lock
#                        criterion").  DR-010 already establishes these are
#                        not the same threshold today.
#   t_lockcrit_us        against the ratified Lock criterion in FULL: 20
#                        consecutive reference cycles with |phi| <= 1 ns AND
#                        |df_out/f_target| <= 0.1 %, reported at the START of
#                        that window, which is how spec/pll.md defines lock
#                        time.  The per-cycle trace is what makes this
#                        directly applicable for the first time -- the two
#                        point samples could not express "20 consecutive
#                        cycles" at all.
#
# and one more that is not a threshold question:
#
#   t_lockflag_us        when v(lock) itself comes up and stays up (>= 90 % of
#                        the rail, run.sh's own ACC_LOCK_FRAC).  The flag is
#                        the observable a consumer actually gates on, and it
#                        lags the phase by the detector's own assert hold-off.
#
# EVERY ONE of these is defined as "...and stays, to the end of the hold",
# scanned BACKWARD from the hold's end.  A forward scan would report the first
# momentary excursion through the threshold during a ringing tail as the
# answer, which is precisely the failure mode an under-damped response would
# produce.  Where a threshold is never satisfied by the hold's end the column
# is emitted as `>hold` -- a LOWER BOUND, explicitly not a number.
#
# The decay law is reported two ways, and the second is the one that adjudicates
# DR-011's stated contradiction:
#   tau_meas_us / fit_r2   a log-linear fit of |phi - phi_settled| over a
#                          FIXED, stated window (1 tau .. 5 tau after the step
#                          edge).  tau_ratio > 1 means SLOWER than the loop's
#                          own dominant pole.  A low fit_r2 means the tail is
#                          not a single exponential at all, whatever tau_meas
#                          says.
#   e_sign_changes         how many times (phi - phi_settled) changes sign
#                          across the hold.  This is completely model-free: a
#                          first-order decay crosses its asymptote zero times,
#                          an under-damped second-order response rings through
#                          it.  `20260901-155456-46b92f8` section 3c's
#                          `under-damped` classification is a claim about
#                          exactly this, made without ever observing it.
# plus relock_decay_law.csv, the per-tau shrink table over the whole hold.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP="$(cd "${HERE}/.." && pwd)"
ROOT="$(cd "${EXP}/../.." && pwd)"

RID="${1:?usage: relock_measurement.sh <record-id> [outdir]}"
OUT="${2:-${EXP}/corners/${RID}}"
SRC="${EXP}/corners/${RID}"
[ -d "${SRC}" ] || { echo "ERROR: ${SRC} not found -- run the campaign first" >&2; exit 1; }

LD_WINDOW="${ROOT}/sim/lock-detector/corners/20260802-050119-c24ee3a/window_edges.csv"
[ -f "${LD_WINDOW}" ] || { echo "ERROR: ${LD_WINDOW} not found" >&2; exit 1; }
PRIOR="${EXP}/corners/20260901-155456-46b92f8"
[ -f "${PRIOR}/supply_steady.csv" ] || { echo "ERROR: ${PRIOR}/supply_steady.csv not found" >&2; exit 1; }

mkdir -p "${OUT}"

# The loop's dominant closed-loop pole, as a FREQUENCY, exactly as spec/pll.md's
# Lock time section states it, and exactly as settling_extrapolation.sh cites
# it.  tau is derived from it rather than typed in, so this script carries one
# cited number and not two.
FP_HZ=17.09e3
# The ratified Lock criterion, spec/pll.md "Lock criterion" -- both thresholds
# and the hold length, cited not invented.
LOCK_PHI_NS=1.0
LOCK_FERR=1e-3
LOCK_CYCLES=20
# run.sh's own ACC_LOCK_FRAC: what counts as the flag being up.
LOCK_FRAC=0.90
# The interpolation noise floor, in ns.  Crossing instants come from linear
# interpolation across at most one closed-loop timestep ceiling (100 ps), so a
# |phi - phi_settled| below this is not a measurement of anything and is
# excluded from the log-linear fit rather than dominating it.
E_FLOOR_NS=0.02

TABLE="${OUT}/relock_measurement.csv"
DECAY="${OUT}/relock_decay_law.csv"

CORNERS="typical 27|ss -40|ff 125"

{
  echo "# campaign: supply-sensitivity (#395, DR-011 Decision 4)"
  echo "# record: ${RID}"
  echo "# generated_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "# Every time column below is MEASURED -- an instant the transient actually reached -- not extrapolated. This is what replaces 20260915-202323-62391c6's two-sample bracket."
  echo "# dominant closed-loop pole f_p = ${FP_HZ} Hz (spec/pll.md 'Lock time': 1/(2 pi R C1) = 17.09 kHz); tau_loop_us = 1e6/(2 pi f_p)"
  echo "# ratified Lock criterion (spec/pll.md 'Lock criterion'): |phi| <= ${LOCK_PHI_NS} ns AND |df_out/f_target| <= ${LOCK_FERR}, held for >= ${LOCK_CYCLES} consecutive reference cycles"
  echo "# ld_assert_ns: this corner's detector assert edge (asserted_up_to_s, sim/lock-detector 20260802-050119-c24ee3a) -- a DIFFERENT threshold from the 1 ns criterion, per DR-010"
  echo "# steady_lock_ok: does THIS corner's undisturbed steady state at the SAME 3.63 V rail assert LOCK? 'no' means structural (spec row 16 / #393) and its t_lockflag_us is a detector result, not a settling one"
  echo "# ALL t_*_us columns are measured from the END of the supply step edge (t_step + t_edge) and mean '...and STAYS satisfied to the end of the hold' (scanned backward from the hold end, so a momentary excursion through the threshold during a ringing tail cannot be reported as the answer)"
  echo "# '>hold' means the threshold was still not satisfied at the hold's end: a LOWER BOUND, not a number"
  echo "# phi_settled_ns: the MEASURED asymptote -- mean phi over the last 20 reference cycles of the hold. Not solved for, not assumed"
  echo "# tau_meas_us / fit_r2: log-linear fit of |phi - phi_settled| over 1 tau .. 5 tau after the step edge, excluding |e| < ${E_FLOOR_NS} ns (interpolation floor). tau_ratio > 1 == SLOWER than the loop's own dominant pole; a low fit_r2 means the tail is not one exponential at all"
  echo "# e_sign_changes: model-free -- how many times (phi - phi_settled) crosses zero across the hold. A first-order decay crosses 0 times; an under-damped second-order response rings through"
  echo "# phi0{7,8}_meas_ns vs phi0{7,8}_trace_ns: the free SELF-CHECK on the trace extraction (the deck's own .meas at instants the trace also covers). phi0{7,8}_prior_ns: the same two measurements in 20260901-155456-46b92f8's escalated run, whose profile is identical up to its own t_ramp -- so these must reproduce too"
  printf 'bundle,temp_c,t_edge_end_s,t_hold_end_s,hold_us_from_edge,hold_tau,n_cycles,'
  printf 'phi_pre_ns,phi_peak_ns,t_phipeak_us,phi_settled_ns,ld_assert_ns,steady_lock_ok,'
  printf 't_relock_assert_us,t_relock_1ns_us,t_lockcrit_us,t_lockflag_us,'
  printf 'tau_loop_us,tau_meas_us,tau_ratio,fit_r2,fit_n,e_sign_changes,'
  printf 'phi07_meas_ns,phi07_trace_ns,phi08_meas_ns,phi08_trace_ns,phi07_prior_ns,phi08_prior_ns\n'
} >"${TABLE}"

{
  echo "# campaign: supply-sensitivity (#395, DR-011 Decision 4) -- per-tau decay table"
  echo "# record: ${RID}"
  echo "# One row per (corner, tau window) across the post-step hold. e_ns = phi_ns - phi_settled_ns, with phi_settled measured over the hold's last 20 cycles."
  echo "# shrink = |e_end| / |e_start| over the window. k_singlepole = exp(-1) = 0.367879, what ONE pole at the loop's own tau gives over one tau."
  echo "# shrink BELOW k_singlepole == closing faster than one pole over that window; ABOVE == slower. This is the table 20260915-202323-62391c6 could not produce from two samples."
  echo "bundle,temp_c,k,t_start_us,t_end_us,e_start_ns,e_end_ns,shrink,k_singlepole"
} >"${DECAY}"

IFS='|' read -r -a CORNER_LIST <<<"${CORNERS}"
for row in "${CORNER_LIST[@]}"; do
  # shellcheck disable=SC2086  # intentional word-splitting of "bundle temp"
  set -- ${row}; bundle="$1"; temp="$2"
  cid="$(printf '%s_%sc_%.2fv' "${bundle}" "${temp}" 3.30)"
  trace="${SRC}/supply_phase_${cid}_relock.csv"
  log="${SRC}/dynrl_${cid}.log"
  [ -f "${trace}" ] || { echo "ERROR: ${trace} not found" >&2; exit 1; }
  [ -f "${log}" ]   || { echo "ERROR: ${log} not found" >&2; exit 1; }

  t_step="$(awk -F= '/^\.param t_step=/{print $2; exit}' "${log}")"
  t_edge="$(awk -F= '/^\.param t_edge=/{print $2; exit}' "${log}")"
  t_ramp="$(awk -F= '/^\.param t_ramp=/{print $2; exit}' "${log}")"
  v_hi="$(awk -F=   '/^\.param v_hi=/{print $2; exit}'   "${log}")"
  [ -n "${t_step}" ] && [ -n "${t_edge}" ] && [ -n "${t_ramp}" ] && [ -n "${v_hi}" ] \
    || { echo "ERROR: could not read the profile instants from ${log}" >&2; exit 1; }

  read -r phi07 t7 <<<"$(awk '/^phi07 /{for(i=1;i<=NF;i++) if($i=="trig=") tg=$(i+1); print $3, tg; exit}' "${log}")"
  read -r phi08 t8 <<<"$(awk '/^phi08 /{for(i=1;i<=NF;i++) if($i=="trig=") tg=$(i+1); print $3, tg; exit}' "${log}")"
  [ -n "${t7}" ] && [ -n "${t8}" ] || { echo "ERROR: could not read phi07/phi08 TRIG instants from ${log}" >&2; exit 1; }

  # The same two measurements in the run this campaign extends, read from ITS
  # committed log -- the reproducibility check, not a result.
  pphi07="$(awk '/^phi07 /{print $3; exit}' "${PRIOR}/dynx_${cid}.log" 2>/dev/null || true)"
  pphi08="$(awk '/^phi08 /{print $3; exit}' "${PRIOR}/dynx_${cid}.log" 2>/dev/null || true)"
  pphi07="${pphi07:-nan}"; pphi08="${pphi08:-nan}"

  ldassert="$(awk -F, -v b="${bundle}" -v t="${temp}" '
    !/^#/ && $1 != "process" && $1==b && $2==t+0 { printf "%.17g", $4*1e9 }' "${LD_WINDOW}")"
  [ -n "${ldassert}" ] || { echo "ERROR: no window_edges.csv row for ${bundle}/${temp}C" >&2; exit 1; }

  slock="$(awk -F, -v b="${bundle}" -v t="${temp}" '
    !/^#/ && $1 != "bundle" && $1==b && $2==t+0 && ($3+0)==3.63 {
      print ($17+0 >= 0.9*3.63) ? "yes" : "no"
    }' "${PRIOR}/supply_steady.csv")"
  [ -n "${slock}" ] || { echo "ERROR: no supply_steady.csv row for ${bundle}/${temp}C at 3.63 V" >&2; exit 1; }

  awk -F, -v b="${bundle}" -v temp="${temp}" -v fp="${FP_HZ}" \
      -v tstep="${t_step}" -v tedge="${t_edge}" -v tramp="${t_ramp}" -v vhi="${v_hi}" \
      -v a="${ldassert}" -v slock="${slock}" \
      -v p7m="${phi07}" -v p8m="${phi08}" -v t7="${t7}" -v t8="${t8}" \
      -v pp7="${pphi07}" -v pp8="${pphi08}" \
      -v lphi="${LOCK_PHI_NS}" -v lferr="${LOCK_FERR}" -v lcyc="${LOCK_CYCLES}" \
      -v lfrac="${LOCK_FRAC}" -v efloor="${E_FLOOR_NS}" -v decay="${DECAY}" '
    function sec(v,  n,s) {
      s = v; sub(/[a-zA-Z]+$/, "", s); n = s + 0;
      if (v ~ /[uU]$/) return n*1e-6;
      if (v ~ /[nN]$/) return n*1e-9;
      if (v ~ /[pP]$/) return n*1e-12;
      if (v ~ /[mM]$/) return n*1e-3;
      return n;
    }
    function abs(x) { return x < 0 ? -x : x }
    # us from the end of the step edge
    function fe(t) { return (t - edge_end)*1e6 }
    BEGIN {
      pi = atan2(0, -1);
      tau_us = 1e6/(2*pi*fp);
      edge_end = sec(tstep) + sec(tedge);
      hold_end = sec(tramp);
      n = 0; npre = 0;
    }
    /^[ \t]*#/ { next }
    /^t_ref_s/ { next }
    {
      t = $1 + 0;
      if (t < edge_end) { PRE_T[++npre] = t; PRE_P[npre] = $2 + 0; next }
      if (t >= hold_end) next;
      n++; T[n] = t; P[n] = $2 + 0; LK[n] = $3 + 0;
    }
    END {
      if (n < 50) { printf "ERROR: only %d in-hold phase samples for %s/%sC\n", n, b, temp > "/dev/stderr"; exit 1 }

      # --- the undisturbed static phase this corner was sitting at ------------
      phi_pre = 0; c = 0;
      for (i = npre; i >= 1 && c < 20; i--) { if (PRE_T[i] < sec(tstep)) { phi_pre += PRE_P[i]; c++ } }
      phi_pre = (c > 0) ? phi_pre/c : 0;

      # --- the excursion peak, and the MEASURED asymptote ---------------------
      phi_peak = P[1]; t_peak = T[1];
      for (i = 1; i <= n; i++) if (abs(P[i]) > abs(phi_peak)) { phi_peak = P[i]; t_peak = T[i] }
      phi_set = 0; for (i = n - 19; i <= n; i++) phi_set += P[i]; phi_set /= 20;

      # --- per-cycle fractional frequency error, centred over +/-10 cycles ----
      # f_out = N*f_fb, so the fractional error of f_out equals that of f_fb,
      # which is -d(phi)/dt.  The window is 20 reference cycles wide -- the
      # same hold the ratified criterion names -- so the two parts of that
      # criterion are evaluated over the same span.
      for (i = 1; i <= n; i++) {
        lo = (i-10 < 1) ? 1 : i-10; hi = (i+10 > n) ? n : i+10;
        FE[i] = -((P[hi] - P[lo])*1e-9)/(T[hi] - T[lo]);
      }

      # --- "...and stays": scan BACKWARD from the hold end --------------------
      ra = ">hold"; for (i = n; i >= 1; i--) if (abs(P[i]) > a)      { if (i < n) ra = sprintf("%.4g", fe(T[i+1])); break } else if (i == 1) ra = sprintf("%.4g", fe(T[1]));
      r1 = ">hold"; for (i = n; i >= 1; i--) if (abs(P[i]) > lphi)   { if (i < n) r1 = sprintf("%.4g", fe(T[i+1])); break } else if (i == 1) r1 = sprintf("%.4g", fe(T[1]));
      lf = ">hold"; for (i = n; i >= 1; i--) if (LK[i] < lfrac*vhi)  { if (i < n) lf = sprintf("%.4g", fe(T[i+1])); break } else if (i == 1) lf = sprintf("%.4g", fe(T[1]));

      # The ratified criterion in full: the first cycle from which BOTH parts
      # hold continuously to the hold end, and for at least lcyc cycles.
      lc = ">hold"; start = 0;
      for (i = n; i >= 1; i--) {
        if (abs(P[i]) > lphi || abs(FE[i]) > lferr) break;
        start = i;
      }
      if (start > 0 && (n - start + 1) >= lcyc) lc = sprintf("%.4g", fe(T[start]));

      # --- decay law ----------------------------------------------------------
      # Fixed, stated fit window: 1 tau .. 5 tau after the step edge.
      sx = sy = sxx = sxy = syy = 0; nf = 0;
      for (i = 1; i <= n; i++) {
        tu = fe(T[i]);
        if (tu < tau_us || tu > 5*tau_us) continue;
        e = abs(P[i] - phi_set);
        if (e < efloor) continue;
        x = tu; y = log(e);
        sx += x; sy += y; sxx += x*x; sxy += x*y; syy += y*y; nf++;
      }
      if (nf >= 10) {
        den = nf*sxx - sx*sx;
        slope = (nf*sxy - sx*sy)/den;
        num = nf*sxy - sx*sy;
        r2 = (num*num)/(den*(nf*syy - sy*sy));
        taum = (slope < 0) ? -1/slope : -1;
      } else { taum = -1; r2 = -1 }

      # model-free: does the tail ring through its own asymptote?
      sgn = 0; nsc = 0;
      for (i = 1; i <= n; i++) {
        e = P[i] - phi_set;
        if (abs(e) < efloor) continue;
        s = (e > 0) ? 1 : -1;
        if (sgn != 0 && s != sgn) nsc++;
        sgn = s;
      }

      # --- the free self-check on the trace extraction -------------------------
      # The trace sample nearest each .meas TRIG instant.
      best7 = 1; best8 = 1;
      for (i = 1; i <= n; i++) {
        if (abs(T[i]-t7) < abs(T[best7]-t7)) best7 = i;
        if (abs(T[i]-t8) < abs(T[best8]-t8)) best8 = i;
      }

      # --- per-tau shrink table ------------------------------------------------
      maxk = int(fe(T[n])/tau_us);
      for (k = 0; k < maxk; k++) {
        ts = k*tau_us; te = (k+1)*tau_us;
        is = 0; ie = 0;
        for (i = 1; i <= n; i++) {
          if (is == 0 && fe(T[i]) >= ts) is = i;
          if (fe(T[i]) <= te) ie = i;
        }
        if (is == 0 || ie <= is) continue;
        es = P[is] - phi_set; ee = P[ie] - phi_set;
        printf "%s,%s,%d,%.4f,%.4f,%.4f,%.4f,%s,%.6f\n", b, temp, k, ts, te, es, ee,
               (abs(es) > efloor) ? sprintf("%.4f", abs(ee)/abs(es)) : "n/a", exp(-1) >> decay;
      }

      printf "%s,%s,%.6g,%.6g,%.4f,%.4f,%d,", b, temp, edge_end, hold_end,
             fe(T[n]), fe(T[n])/tau_us, n;
      printf "%.4f,%.4f,%.4f,%.4f,%.4g,%s,", phi_pre, phi_peak, fe(t_peak), phi_set, a, slock;
      printf "%s,%s,%s,%s,", ra, r1, lc, lf;
      printf "%.4f,%s,%s,%s,%d,%d,", tau_us,
             (taum > 0) ? sprintf("%.4f", taum) : "n/a",
             (taum > 0) ? sprintf("%.4f", taum/tau_us) : "n/a",
             (r2 >= 0) ? sprintf("%.4f", r2) : "n/a", nf, nsc;
      printf "%.4f,%.4f,%.4f,%.4f,%s,%s\n",
             p7m*1e9, P[best7], p8m*1e9, P[best8],
             (pp7 == "nan") ? "nan" : sprintf("%.4f", pp7*1e9),
             (pp8 == "nan") ? "nan" : sprintf("%.4f", pp8*1e9);
    }' "${trace}" >>"${TABLE}"
done

echo "relock_measurement: wrote ${TABLE}"
cat "${TABLE}"
echo
echo "relock_measurement: wrote ${DECAY}"
cat "${DECAY}"
