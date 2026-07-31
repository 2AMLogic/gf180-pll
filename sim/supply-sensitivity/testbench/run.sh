#!/usr/bin/env bash
# gf180-pll :: supply-sensitivity :: closed-loop supply sensitivity and power
#
# The campaign sim/README.md reserves for #14: what the WHOLE PLL does across
# the ratified 3.3 V +/- 10 % supply range, and what it costs in power while it
# does it.  Four things, each with its own testbench run and its own criterion:
#
#   1. output frequency vs. supply, over the full 45-point PVT grid, reported
#      as the deviation from the same corner's nominal-supply value;
#   2. static phase offset vs. supply, over the same grid, measured two
#      independent ways (REF->FB skew, and the UP/DN pulse-WIDTH difference
#      that produces it) against the POST-#24 charge pump;
#   3. does the loop stay locked through a supply STEP and a supply RAMP, and
#      how much disturbance couples through from the VCO supply pushing #8
#      already measured open-loop;
#   4. quiescent and dynamic supply current with the loop locked at 100 MHz,
#      broken down per supply domain, against the draft < 5 mW target.
#
# DR-002 Decision 3 ratifies 3.3 V thick-oxide only for v1, so the 2.97 /
# 3.30 / 3.63 V axis of the default corner grid IS the complete supply-axis
# requirement -- there is no separate 1.8 V or 5 V supply-flavour sweep to run.
#
# The DUT is design/pll_top.sch (#52), assembled by
# sim/lib/assemble_closed_loop.sh.  This campaign does not build a top level of
# its own; nothing here is a hand-transcribed copy of the design.
#
# Usage:
#   ./run.sh                 # run everything and mint a record
#   ./run.sh --check         # one nominal point, print metrics, write NO record
#   ./run.sh --op-table      # print the derived operating-point table and exit
#   SIM_FORCE=1 ./run.sh     # ignore cached runs in work/ and re-simulate
#   SIM_JOBS=8 ./run.sh      # override the parallel job count
#
#   SIM_SUPERSEDES=<record-id> SIM_SUPERSEDES_NOTE='<why>' ./run.sh
#                            mint with a **Supersedes** field (sim/README.md ::
#                            "Status / supersession language").
#
# Every run is resumable: a completed run is reused only on an exact match of
# the deck mtime AND the full parameter list, never on the deck alone.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP="$(cd "${HERE}/.." && pwd)"
ROOT="$(cd "${EXP}/../.." && pwd)"
# shellcheck source=../../lib/simenv.sh
. "${ROOT}/sim/lib/simenv.sh"
# shellcheck source=../../lib/assemble_closed_loop.sh
. "${ROOT}/sim/lib/assemble_closed_loop.sh"

WORK="${EXP}/work"
DUT_LOCK="${WORK}/dut_lock.sp"
DUT_DYN="${WORK}/dut_dyn.sp"

# ---------------------------------------------------------------------------
# The operating point, and where every number comes from.
# ---------------------------------------------------------------------------
# KFOUT   100 MHz output -- the frequency #14's power criterion names, and
#         inside DR-002 Decision 2's ratified 10-200 MHz v1 band.
# KN      N = 8, mid of the ratified 4-64 range (DR-001 Decision 3).
# KFREF   12.5 MHz reference (= 100 MHz / 8), inside DR-002 Decision 1's
#         ratified 1-25 MHz range.
# KTRIM   Icp trim code 2 (three unit legs), the nominal setting
#         design/README.md characterises the charge pump at, and the setting
#         sim/loop-dynamics shows meeting both the 45 deg phase-margin
#         criterion and the f_c < f_ref/10 ceiling across the 8-16 MHz
#         reference decade this operating point sits in.
KFOUT=100e6
KN=8
KFREF=12.5e6
KTRIM=2

# The SECOND frequency point, used only for the quiescent/dynamic power split
# (see "Quiescent vs. dynamic" below).  Same N, half the reference, so f_ref
# and f_out scale together and a two-point fit in f_out is unambiguous.
KFOUT2=50e6
KFREF2=6.25e6

# Transient controls, shared by every steady-state run.
# KTMAX   400 ps ceiling on the internal timestep.  Set by the CHARGE PUMP as
#         in sim/pll-top-smoke -- the PFD's minimum UP/DN pulse is 1.1-1.9 ns
#         (24-inverter reset chain, design/README.md) and the charge in those
#         pulses IS the loop gain -- and tightened from that campaign's 500 ps
#         because this one MEASURES those pulse widths (criterion 2), so the
#         narrower of the two pulses must be resolved by several timesteps and
#         not merely integrated correctly.  At 100 MHz it is 25 points per
#         output cycle, and ngspice's own local-truncation-error control takes
#         the step well below this ceiling through every edge -- the ceiling
#         only bounds the quiet stretches between them.
# KTSTOP  54 us.  The loop's slowest pole is 1/(2*pi*R*C1) = 17.1 kHz
#         (sim/loop-dynamics), i.e. tau = 9.3 us; the warm start below places
#         the control node within ~0.05 V of its lock point, so ~3.4 tau of
#         settling to reach the 1e-3 residual the lock criterion demands.
#         KTA at 32 us is 3.4 tau, KTB at 44 us is 4.7 tau, and the run has
#         10 us left after KTB for the frequency measurements (200 CLK cycles
#         = 2 us at 100 MHz, 4 us at 50 MHz; 20 FB cycles = 1.6 us / 3.2 us).
# KTA/KTB Both land on a reference HALF-period for BOTH reference frequencies
#         (12.5 MHz: tstart = 40 ns, k = 399 and 549; 6.25 MHz: tstart = 80 ns,
#         k = 199 and 274), so "the first REF rise after t" and "the first FB
#         rise after t" are the same cycle's pair at either setting.
KTSTOP=54u
KTSTEP=20n
KTMAX=400p
KTA=32.0u
KTB=44.0u

# Supply step/ramp profile (criterion 3).  One transient carries both events.
# KD_STEP  a 3.30 -> 3.63 V step with a 100 ns edge: 100 ns is ~1/40 of the
#          loop's own response time at f_c ~ f_ref/22 = 570 kHz, so it is a
#          step as far as the loop is concerned, while staying slow enough that
#          the rail is not a delta function the integrator cannot resolve.
# KD_RAMP  3.63 -> 2.97 V over 40 us, i.e. 16.5 mV/us.  Deliberately SLOWER
#          than the loop (40 us is ~23 loop time constants) so it tests
#          tracking rather than transient rejection: the two events together
#          bracket the loop's bandwidth from both sides, which a single rate
#          could not.
# The rate is stated here rather than left implicit because #14's acceptance
# criterion requires the record to name it.
KD_LO=3.30
KD_HI=3.63
KD_END=2.97
KD_TSTEP=40u
KD_TEDGE=100n
KD_TRAMP=80u
KD_TREND=120u
KD_TSTOP=160u
KD_DECIM=40e-9

# Acceptance thresholds.  Stated here, before the run, not discovered from it.
ACC_FERR=1e-3          # |residual fractional frequency error| in lock
ACC_PHI_FRAC=0.02      # |static phase error| as a fraction of a reference period
ACC_NTOL=0.01          # |f_out/f_fb - N|
ACC_LOCK_FRAC=0.90     # LOCK flag level in the late window, fraction of the rail
ACC_VCTRL_LO=0.9       # DR-001 Decision 2's usable control window
ACC_VCTRL_HI=2.4
ACC_PWR_MW=5.0         # draft power target (placeholder pending #1)
ACC_FDEV_PPM=1000      # |f_out(vdd) - f_out(3.30 V)| / f_out(3.30 V), ppm

# #8's open-loop VCO supply-pushing figures, CITED not re-derived (#14's
# acceptance criterion says so in as many words).  Source:
# sim/vco-tuning-range/records/20260731-184845-0a12e6c.md, sections 1 and 2.
CITE_VCO_RECORD=20260731-184845-0a12e6c
CITE_PUSH_WORST=-50.7          # %/V, static, ss/-40C band 4
CITE_PUSH_MEDIAN=-39.4         # %/V, static, median over the grid
CITE_STEP_WORST=-47.7          # MHz/V, transient, 0.1 V step, band 5 ~100 MHz

# #8's measured f(Vctrl) table -- the source of both the band code and the
# warm-start control voltage for every corner below.  Using the committed
# evidence rather than a fresh sweep is the point: the operating point this
# campaign runs at is derived from a citable record, and a reader can check the
# derivation without re-simulating anything.
VCO_TUNING="${ROOT}/sim/vco-tuning-range/corners/20260731-175947-0a12e6c/vco_tuning.csv"

# Passive sections.  Named explicitly rather than defaulted: sim/README.md
# warns that a MOS-only sweep silently pins the passives at typical, and this
# DUT contains the loop filter whose R and C set the loop bandwidth.  Here they
# ARE all typical -- the point is that the record says so because the run put
# them there.  The justification for not sweeping them is in the record.
PASSIVES="res_typical,moscap_typical,mimcap_typical"

libs_for() { echo "$1,${PASSIVES}"; }

# ---------------------------------------------------------------------------
# Operating-point derivation
# ---------------------------------------------------------------------------
# For each (bundle, temperature) pick ONE band code -- band select is a static
# input with no calibration FSM (DR-001 Decision 2), so it cannot be re-chosen
# when the supply moves, and picking it per supply would measure a different
# configuration at each supply point and call the difference "supply
# sensitivity".  The chosen code is the one that reaches the target frequency
# at ALL THREE supplies with the control voltage as close to mid-window as
# possible; the per-supply control voltage it implies is the warm start.
#
# Prints: bundle,temp_c,band,vctrl_2.97,vctrl_3.30,vctrl_3.63
# A (bundle, temperature) row for which NO band reaches the target at all three
# supplies inside the search window is printed with band = -1, and the caller
# treats that as a campaign-level finding rather than papering over it.
derive_op_points() {
  local target="$1" lo="${2:-0.85}" hi="${3:-2.70}"
  awk -F, -v target="${target}" -v LO="${lo}" -v HI="${hi}" '
    !/^#/ && $1 != "bundle" {
      b=$1; t=$2; v=$3; bd=$4; vc=$5; f=$6;
      if (b == "all-slow" || b == "all-fast") next;   # composite bundles are
                                                      # not on the 45-point grid
      k = b "|" t "|" v "|" bd; n[k]++; VC[k,n[k]]=vc; F[k,n[k]]=f;
    }
    END {
      # Vctrl at the target frequency, by linear interpolation inside the one
      # bracketing interval of the measured f(Vctrl) curve.  No extrapolation:
      # a curve that does not bracket the target simply has no entry.
      for (k in n) {
        for (i = 1; i < n[k]; i++) {
          f1 = F[k,i]; f2 = F[k,i+1];
          if ((f1 - target) * (f2 - target) <= 0 && f1 != f2)
            V[k] = VC[k,i] + (target - f1) * (VC[k,i+1] - VC[k,i]) / (f2 - f1);
        }
      }
      nb = split("typical ff ss fs sf", BU, " ");
      nt = split("-40 27 125", TE, " ");
      ns = split("2.97 3.30 3.63", SU, " ");
      mid = 0.5 * (LO + HI);
      for (bi = 1; bi <= nb; bi++) for (ti = 1; ti <= nt; ti++) {
        bestband = -1; bestcost = 1e9; bestline = ",,,";
        for (bd = 0; bd <= 7; bd++) {
          ok = 1; cost = 0; line = "";
          for (si = 1; si <= ns; si++) {
            kk = BU[bi] "|" TE[ti] "|" SU[si] "|" bd;
            if (!(kk in V)) { ok = 0; break }
            vv = V[kk];
            if (vv < LO || vv > HI) { ok = 0; break }
            d = vv - mid; if (d < 0) d = -d;
            if (d > cost) cost = d;
            line = line sprintf(",%.4f", vv);
          }
          if (ok && cost < bestcost) { bestcost = cost; bestband = bd; bestline = line }
        }
        printf "%s,%s,%d%s\n", BU[bi], TE[ti], bestband, bestline;
      }
    }' "${VCO_TUNING}"
}

# ---------------------------------------------------------------------------
# One steady-state run.
#   --one-lock <bundle> <temp> <vdd> <band> <vctrl0> <fout> <fref> <sumfile>
# ---------------------------------------------------------------------------
if [ "${1:-}" = "--one-lock" ]; then
  shift
  bundle="$1"; temp="$2"; vdd="$3"; band="$4"; vc0="$5"; fout="$6"; fref="$7"; sum="$8"
  kind="f$(awk -v f="${fout}" 'BEGIN{printf "%03d", f/1e6}')"
  tag="${kind}_${bundle}_T${temp}_V${vdd}"; tag="${tag//./p}"; tag="${tag//-/m}"
  rundir="${WORK}/${tag}"; log="${rundir}/ngspice.log"
  libs="$(libs_for "${bundle}")"

  params=( "vsup=${vdd}" "fref=${fref}" "nratio=${KN}" "vctrl0=${vc0}"
           "tstop=${KTSTOP}" "tstep=${KTSTEP}" "tmax=${KTMAX}"
           "ta=${KTA}" "tb=${KTB}" )
  # shellcheck disable=SC2207
  params+=( $(cloop_band_params "${band}") )
  # shellcheck disable=SC2207
  params+=( $(cloop_trim_params "${KTRIM}") )
  # shellcheck disable=SC2207
  params+=( $(cloop_divider_params "${KN}") )
  sig="${libs}|${temp}|${params[*]}"

  if [ -z "${SIM_FORCE:-}" ] && [ -f "${log}" ] && [ "${log}" -nt "${DUT_LOCK}" ] \
     && [ "$(cat "${rundir}/.sig" 2>/dev/null)" = "${sig}" ] \
     && grep -q "Total analysis time" "${log}" 2>/dev/null; then
    :
  else
    simenv_run_deck "${DUT_LOCK}" "${WORK}" "${tag}" "${libs}" "${temp}" "${params[@]}" \
      >/dev/null 2>&1 || true
    grep -q "Total analysis time" "${log}" 2>/dev/null || {
      echo "ERROR: ngspice did not complete ${tag} (see ${log})" >&2; exit 1; }
    printf '%s' "${sig}" >"${rundir}/.sig"
  fi

  m() { simenv_meas "${log}" "$1"; }
  printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n' \
    "${bundle}" "${temp}" "${vdd}" "${fout}" "${band}" "${KTRIM}" "${fref}" "${KN}" "${vc0}" \
    "$(m fout)" "$(m ffb)" "$(m nmeas)" "$(m ferr)" "$(m phi_b)" \
    "$(m skew1)" "$(m skew2)" "$(m skew3)" "$(m wup1)" "$(m wdn1)" \
    "$(m vctrl_avg)" "$(m vctrl_min)" "$(m vctrl_max)" "$(m lock_lvl)" \
    "$(m i_core)" "$(m i_vco)" "$(m i_div)" >"${sum}"
  exit 0
fi

# ---------------------------------------------------------------------------
# One supply step/ramp run.
#   --one-dyn <bundle> <temp> <band> <vctrl0> <sumfile> <wavefile>
# ---------------------------------------------------------------------------
if [ "${1:-}" = "--one-dyn" ]; then
  shift
  bundle="$1"; temp="$2"; band="$3"; vc0="$4"; sum="$5"; wave="$6"
  tag="dyn_${bundle}_T${temp}"; tag="${tag//./p}"; tag="${tag//-/m}"
  rundir="${WORK}/${tag}"; log="${rundir}/ngspice.log"
  libs="$(libs_for "${bundle}")"

  # Snap every phase probe onto a reference HALF-period, tstart + (k+0.5)/f_ref
  # with tstart = 0.5/f_ref, so REF and FB rises paired by a probe are the same
  # cycle's and the measurement cannot alias by a whole reference period.
  snap() { awk -v t="$1" -v f="${KFREF}" \
    'BEGIN{ tr=1/f; ts=0.5*tr; k=int((t-ts)/tr - 0.5 + 0.5); if(k<0)k=0;
            printf "%.12g", ts + (k+0.5)*tr }'; }
  P=()
  for t in 28e-6 38e-6 40.6e-6 42e-6 46e-6 54e-6 68e-6 78e-6 100e-6 118e-6 130e-6 155e-6; do
    P+=( "$(snap "${t}")" )
  done

  params=( "vsup=${KD_LO}" "fref=${KFREF}" "nratio=${KN}" "vctrl0=${vc0}"
           "v_lo=${KD_LO}" "v_hi=${KD_HI}" "v_end=${KD_END}"
           "t_step=${KD_TSTEP}" "t_edge=${KD_TEDGE}"
           "t_ramp=${KD_TRAMP}" "t_rend=${KD_TREND}"
           "tstop=${KD_TSTOP}" "tstep=${KTSTEP}" "tmax=${KTMAX}" )
  for i in $(seq 0 11); do params+=( "p$((i+1))=${P[${i}]}" ); done
  # shellcheck disable=SC2207
  params+=( $(cloop_band_params "${band}") )
  # shellcheck disable=SC2207
  params+=( $(cloop_trim_params "${KTRIM}") )
  # shellcheck disable=SC2207
  params+=( $(cloop_divider_params "${KN}") )
  sig="${libs}|${temp}|${params[*]}"

  if [ -z "${SIM_FORCE:-}" ] && [ -f "${log}" ] && [ "${log}" -nt "${DUT_DYN}" ] \
     && [ "$(cat "${rundir}/.sig" 2>/dev/null)" = "${sig}" ] \
     && grep -q "Total analysis time" "${log}" 2>/dev/null; then
    :
  else
    simenv_run_deck "${DUT_DYN}" "${WORK}" "${tag}" "${libs}" "${temp}" "${params[@]}" \
      >/dev/null 2>&1 || true
    grep -q "Total analysis time" "${log}" 2>/dev/null || {
      echo "ERROR: ngspice did not complete ${tag} (see ${log})" >&2; exit 1; }
    printf '%s' "${sig}" >"${rundir}/.sig"
  fi

  m() { simenv_meas "${log}" "$1"; }
  {
    printf '%s,%s,%s,%s' "${bundle}" "${temp}" "${band}" "${vc0}"
    for k in phi01 phi02 phi03 phi04 phi05 phi06 phi07 phi08 phi09 phi10 phi11 phi12 \
             ferr_lo ferr_hi ferr_end fout_lo fout_hi fout_end fout_s fout_r \
             vc_lo vc_hi vc_end vc_smax vc_smin vc_rmax vc_rmin vc_all_max vc_all_min \
             lock_lo lock_stp lock_hi lock_rmp lock_end lock_min \
             i_core_lo i_vco_lo i_div_lo i_core_hi i_vco_hi i_div_hi \
             i_core_end i_vco_end i_div_end; do
      printf ',%s' "$(m "${k}")"
    done
    printf '\n'
  } >"${sum}"

  # sim/README.md's waveform rule: the disturbance transient IS the argument
  # for this criterion, so keep it -- decimated, as a CSV of the four signals
  # that carry it, never as a rawfile.  Nearest-sample decimation, no
  # interpolation, so every committed row is a value ngspice computed.
  {
    echo "# gf180-pll :: supply-sensitivity :: supply step/ramp transient"
    echo "# corner: ${bundle} / ${temp} C, band ${band}, N=${KN}, f_ref=${KFREF} Hz"
    echo "# profile: ${KD_LO} V -> step(${KD_TEDGE}) -> ${KD_HI} V @ ${KD_TSTEP};"
    echo "#          ramp ${KD_TRAMP}..${KD_TREND} -> ${KD_END} V; hold to ${KD_TSTOP}"
    echo "# decimation: nearest sample at ${KD_DECIM} s from the full ngspice trace"
    echo "t_s,vctrl_v,lock_v,vdd_v,fb_v"
    awk -v d="${KD_DECIM}" '
      /^[ \t]*[-0-9]/ {
        t = $1 + 0;
        if (t + 1e-15 >= next_t) {
          printf "%.9g,%.6g,%.6g,%.6g,%.6g\n", t, $2, $4, $6, $8;
          next_t = t + d;
        }
      }' "${rundir}/supply_transient_full.csv"
  } >"${wave}"
  exit 0
fi

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
simenv_require_tools
[ -f "${VCO_TUNING}" ] || {
  echo "ERROR: ${VCO_TUNING} missing -- this campaign derives its operating" >&2
  echo "       point from #8's committed f(Vctrl) evidence, not from a fresh sweep." >&2
  exit 1; }

mkdir -p "${WORK}"
cloop_assemble "${HERE}/tb_supply_lock.sp" "${DUT_LOCK}"
cloop_assemble "${HERE}/tb_supply_dyn.sp"  "${DUT_DYN}"

OPTAB="${WORK}/op_100.csv"
OPTAB2="${WORK}/op_050.csv"
derive_op_points "${KFOUT}"  >"${OPTAB}"
derive_op_points "${KFOUT2}" >"${OPTAB2}"

if [ "${1:-}" = "--op-table" ]; then
  echo "operating points for f_out = ${KFOUT} Hz  (bundle,temp,band,vctrl@2.97,@3.30,@3.63)"
  cat "${OPTAB}"
  echo
  echo "operating points for f_out = ${KFOUT2} Hz"
  cat "${OPTAB2}"
  exit 0
fi

if [ "${1:-}" = "--check" ]; then
  read -r _b _t band v297 v330 v363 <<<"$(awk -F, '$1=="typical"&&$2=="27"{print $1,$2,$3,$4,$5,$6}' "${OPTAB}")"
  echo "supply-sensitivity --check: typical/27C/3.30V, band ${band}, vctrl0 ${v330}"
  tmp="$(mktemp)"
  "${HERE}/run.sh" --one-lock typical 27 3.30 "${band}" "${v330}" "${KFOUT}" "${KFREF}" "${tmp}"
  cat "${tmp}"; rm -f "${tmp}"
  echo "supply-sensitivity: --check, no record written"
  exit 0
fi

# --- job list: the full 45-point grid at 100 MHz -----------------------------
JOBS100="${WORK}/jobs_100.txt"; : >"${JOBS100}"
NOBAND=""
while IFS=, read -r bundle temp band v297 v330 v363; do
  if [ "${band}" = "-1" ]; then
    NOBAND="${NOBAND}${bundle}/${temp}C "
    continue
  fi
  echo "${bundle} ${temp} 2.97 ${band} ${v297} ${KFOUT} ${KFREF} ${WORK}/s100_${bundle}_${temp}_2.97.csv" >>"${JOBS100}"
  echo "${bundle} ${temp} 3.30 ${band} ${v330} ${KFOUT} ${KFREF} ${WORK}/s100_${bundle}_${temp}_3.30.csv" >>"${JOBS100}"
  echo "${bundle} ${temp} 3.63 ${band} ${v363} ${KFOUT} ${KFREF} ${WORK}/s100_${bundle}_${temp}_3.63.csv" >>"${JOBS100}"
done <"${OPTAB}"

# --- job list: the quiescent/dynamic power split -----------------------------
# QUIESCENT VS. DYNAMIC.  There is no "switch the clock off" state to measure a
# quiescent current in: the ring VCO's starving current IS its oscillation
# current, and a PLL with a stopped reference is not a locked PLL.  So the
# split is measured the way it is defined -- as the frequency-INDEPENDENT and
# frequency-PROPORTIONAL parts of the same current -- by locking the same loop
# at a second output frequency and fitting I(f) = I_q + k*f per domain.  The
# second point halves BOTH f_out and f_ref, so every switching node in the
# block scales together and the fit has one slope rather than two.
#
# Reduced grid, and why: the split is a decomposition of a total the 45-point
# grid above already reports at every corner, and its own corner dependence is
# second-order (it re-attributes the same measured current between two
# columns).  It is run over the supply and temperature axes at the `typical`
# process bundle -- 9 points -- so the supply axis this campaign exists to
# sweep is covered at full resolution.
JOBS050="${WORK}/jobs_050.txt"; : >"${JOBS050}"
while IFS=, read -r bundle temp band v297 v330 v363; do
  [ "${bundle}" = "typical" ] || continue
  [ "${band}" = "-1" ] && continue
  echo "${bundle} ${temp} 2.97 ${band} ${v297} ${KFOUT2} ${KFREF2} ${WORK}/s050_${bundle}_${temp}_2.97.csv" >>"${JOBS050}"
  echo "${bundle} ${temp} 3.30 ${band} ${v330} ${KFOUT2} ${KFREF2} ${WORK}/s050_${bundle}_${temp}_3.30.csv" >>"${JOBS050}"
  echo "${bundle} ${temp} 3.63 ${band} ${v363} ${KFOUT2} ${KFREF2} ${WORK}/s050_${bundle}_${temp}_3.63.csv" >>"${JOBS050}"
done <"${OPTAB2}"

# --- job list: supply step/ramp ---------------------------------------------
# Three corners, chosen as the extremes of the steady-state grid rather than as
# a convenience sample: nominal, the slow/cold corner and the fast/hot corner.
# Justified in the record; the step/ramp criterion is a stays-locked question,
# and a corner at which the loop stays locked through the profile at both
# extremes of process and temperature answers it in a way 45 repetitions of the
# same answer would not improve.
JOBSDYN="${WORK}/jobs_dyn.txt"; : >"${JOBSDYN}"
for pick in "typical 27" "ss -40" "ff 125"; do
  set -- ${pick}
  b="$1"; t="$2"
  row="$(awk -F, -v b="${b}" -v t="${t}" '$1==b && $2==t {print}' "${OPTAB}")"
  [ -n "${row}" ] || continue
  band="$(echo "${row}" | cut -d, -f3)"
  v330="$(echo "${row}" | cut -d, -f5)"
  [ "${band}" = "-1" ] && continue
  echo "${b} ${t} ${band} ${v330} ${WORK}/sdyn_${b}_${t}.csv ${WORK}/wave_${b}_${t}.csv" >>"${JOBSDYN}"
done

N100=$(wc -l <"${JOBS100}" | tr -d ' ')
N050=$(wc -l <"${JOBS050}" | tr -d ' ')
NDYN=$(wc -l <"${JOBSDYN}" | tr -d ' ')
echo "supply-sensitivity: ${N100} steady-state runs @ ${KFOUT} Hz, ${N050} @ ${KFOUT2} Hz (power split), ${NDYN} step/ramp runs; $(simenv_jobs) parallel jobs"
[ -z "${NOBAND}" ] || echo "supply-sensitivity: NO single band spans +/-10 % at: ${NOBAND}"

# shellcheck disable=SC2016
xargs -P "$(simenv_jobs)" -L 1 \
  "${BASH:-/bin/bash}" -c 'exec "$0" --one-lock "$@"' "${HERE}/run.sh" <"${JOBS100}"
# shellcheck disable=SC2016
xargs -P "$(simenv_jobs)" -L 1 \
  "${BASH:-/bin/bash}" -c 'exec "$0" --one-lock "$@"' "${HERE}/run.sh" <"${JOBS050}"
# shellcheck disable=SC2016
xargs -P "$(simenv_jobs)" -L 1 \
  "${BASH:-/bin/bash}" -c 'exec "$0" --one-dyn "$@"' "${HERE}/run.sh" <"${JOBSDYN}"

got100=$(cat "${WORK}"/s100_*.csv 2>/dev/null | wc -l | tr -d ' ')
got050=$(cat "${WORK}"/s050_*.csv 2>/dev/null | wc -l | tr -d ' ')
gotdyn=$(cat "${WORK}"/sdyn_*.csv 2>/dev/null | wc -l | tr -d ' ')
[ "${got100}" -eq "${N100}" ] || { echo "ERROR: expected ${N100} rows @100 MHz, got ${got100}" >&2; exit 1; }
[ "${got050}" -eq "${N050}" ] || { echo "ERROR: expected ${N050} rows @50 MHz, got ${got050}" >&2; exit 1; }
[ "${gotdyn}" -eq "${NDYN}" ] || { echo "ERROR: expected ${NDYN} step/ramp rows, got ${gotdyn}" >&2; exit 1; }

exec "${HERE}/report.sh" "${WORK}" "${EXP}" "${HERE}"
