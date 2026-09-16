#!/usr/bin/env bash
# gf180-pll :: supply-sensitivity :: the settling-escalation campaign for the
# 15 over-bound, unsettled corners (#399, DR-012 Decision 6)
#
#   ./static_phase_settling_campaign.sh [record-id]
#
# `20260916-051708-8cedbba.md` (#394) read `20260901-155456-46b92f8`'s
# 45-point steady-state grid as a population and found that 15 of the 17 rows
# over the ratified `spec/pll.md` Lock criterion (<= 1 ns) were STILL MOVING
# when sampled at the grid's 12.0 us / 0.69-1.03 tau window -- `phi_b` there is
# an upper bound on a decaying tail, not a static offset, and that record
# explicitly declined to estimate where each settles. This script runs the
# measurement #394 named as owed: `run.sh`'s existing 36.8 us (3.96 tau)
# settling escalation, at exactly those 15 corners and no others.
#
# ---------------------------------------------------------------------------
# SCOPE, decided before the run (mirrors relock_campaign.sh's discipline)
# ---------------------------------------------------------------------------
# CORNERS: the 15 rows of
# `corners/20260916-051708-8cedbba/static_phase_widened.csv` with
# `over_ratified=yes` and `settled=no`. Band code and the warm-start `vctrl0`
# for each (bundle, temp, vdd) triple are READ FROM the original
# `20260901-155456-46b92f8` run's committed logs
# (`corners/20260901-155456-46b92f8/f100_<bundle>_<temp>c_<vdd>v.log`,
# `.param vctrl0=...`, decoded `b0_code`/`b1_code`/`b2_code`), not re-derived
# or re-calibrated -- this campaign starts from the IDENTICAL warm state the
# original 12.0 us run did, so the only thing that differs between the two
# records is transient length and sampling window, not operating point.
#
# LENGTH: `run.sh`'s own settling-escalation target -- `SIM_TSTOP`/`SIM_TA`/
# `SIM_TB` set to 36.8u/31.2u/34.4u, i.e. exactly `KTSTOP_X`/`KTA_X`/`KTB_X` in
# `run.sh`. No new testbench, no new criterion: this is `run.sh --one-lock`
# invoked directly at the escalated length, which is what the runner's own
# automatic escalation would do if it were run over the full grid -- avoided
# here because the full grid escalates 30 of 45 rows under the runner's
# current (correct, post-#394) phase gate, which is a different and much more
# expensive campaign than the one this issue scopes.
#
# COST: the unescalated 12.0 us run took 6852-12128 s of ngspice analysis time
# per corner in the source record (process/temperature dependent: `fs`/`sf`
# ~7000-7400 s, `ff`/`ss`/`typical` ~10200-12100 s). The escalated length is
# ~3.07x the transient (36.8/12.0), so each of the 15 runs individually is of
# order several hours. All 15 are independent single-threaded ngspice
# processes (this campaign's `run.sh` already pins OMP threading off via
# `simenv_apply_omp_pin`) and run CONCURRENTLY, bounded by `SIM_JOBS`
# (default: host core count) -- see run.sh's own `simenv_jobs()`.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP="$(cd "${HERE}/.." && pwd)"
ROOT="$(cd "${EXP}/../.." && pwd)"
# shellcheck source=../../lib/simenv.sh
. "${ROOT}/sim/lib/simenv.sh"

WORK="${EXP}/work"
RID="${1:-$(simenv_record_id)}"
OUT="${EXP}/corners/${RID}"
SNAPDIR="${EXP}/netlist-snapshots"
PRIOR="${EXP}/corners/20260901-155456-46b92f8"
WIDENED="${EXP}/corners/20260916-051708-8cedbba/static_phase_widened.csv"

# The 15 scoped corners: bundle temp vdd band vctrl0
# band and vctrl0 read from PRIOR's committed f100_<bundle>_<temp>c_<vdd>v.log
# (.param b0_code/b1_code/b2_code decoded to band = b2*4+b1*2+b0, and
# .param vctrl0 verbatim) -- see SCOPE above.
CORNERS=(
  "ff      125 3.30 5 2.0230"
  "ff      125 3.63 5 2.2906"
  "fs      -40 3.30 6 1.2285"
  "fs      -40 3.63 6 1.4509"
  "fs      27  3.30 5 2.1112"
  "sf      -40 2.97 6 0.9945"
  "sf      -40 3.30 6 1.2648"
  "sf      -40 3.63 6 1.4964"
  "sf      27  3.63 5 2.5484"
  "sf      125 2.97 5 1.5891"
  "ss      27  3.63 5 2.3600"
  "ss      125 3.30 5 1.7098"
  "typical 27  3.30 5 2.1618"
  "typical 125 3.30 5 1.8846"
  "typical 125 3.63 5 2.1827"
)

# The escalation target -- run.sh's own KTSTOP_X/KTA_X/KTB_X, stated here as
# the SIM_TSTOP/SIM_TA/SIM_TB overrides --one-lock actually reads.
export SIM_TSTOP=36.8u
export SIM_TA=31.2u
export SIM_TB=34.4u

KFOUT=100e6
KFREF=12.5e6

simenv_require_tools
mkdir -p "${WORK}" "${OUT}" "${SNAPDIR}"

# --one-lock (called below) requires WORK/dut_lock.sp to already exist --
# it is assembled by run.sh's own Main, which --one-lock's code path (checked
# before Main) never reaches on a direct invocation. `--op-table` is the
# cheapest call that reaches Main (no simulation) and guarantees the DUT
# snapshot this campaign needs is in place and current.
"${HERE}/run.sh" --op-table >/dev/null

echo "static_phase_settling_campaign: record ${RID}; ${#CORNERS[@]} corners, tstop=${SIM_TSTOP} ta=${SIM_TA} tb=${SIM_TB}"

# --- 1. run, concurrently ---------------------------------------------------
pids=()
for row in "${CORNERS[@]}"; do
  # shellcheck disable=SC2086  # intentional word-splitting of the corner row
  set -- ${row}; b="$1"; t="$2"; v="$3"; band="$4"; vc0="$5"
  sumfile="${WORK}/s100settle_${b}_${t}_${v}.csv"
  "${HERE}/run.sh" --one-lock "${b}" "${t}" "${v}" "${band}" "${vc0}" \
    "${KFOUT}" "${KFREF}" "${sumfile}" &
  pids+=("$!")
done
rc=0
for p in "${pids[@]}"; do wait "${p}" || rc=1; done
[ "${rc}" -eq 0 ] || { echo "ERROR: at least one settling-escalation run failed" >&2; exit 1; }

# --- 2. archive --------------------------------------------------------------
cp "${WORK}/dut_lock.sp" "${SNAPDIR}/${RID}.spice"
SUMMARY="${OUT}/static_phase_settled.csv"
{
  echo "# campaign: supply-sensitivity settling escalation (#399, DR-012 Decision 6)"
  echo "# source corner selection (read-only): sim/supply-sensitivity/corners/20260916-051708-8cedbba/static_phase_widened.csv (over_ratified=yes, settled=no)"
  echo "# escalated length: tstop=${SIM_TSTOP} ta=${SIM_TA} tb=${SIM_TB} (3.96/3.35/3.70 tau, KTAU=9.3u)"
  echo "# ratified criterion: |static phase at the PFD inputs| <= 1 ns (spec/pll.md, Lock criterion)"
  echo "# settled: 'no' when |d_phi_window_ns| > 0.1 ns (same 10%-of-criterion threshold as static_phase_widened.csv)"
  echo "bundle,temp_c,vdd_v,band,vctrl0_v,fout_meas_hz,ffb_hz,nmeas,ferr,phi_b_ns,vctrl_avg_v,lock_lvl,phi_a_ns,d_phi_window_ns,settled,over_ratified,tstop,ta,tb"
} >"${SUMMARY}"

for row in "${CORNERS[@]}"; do
  # shellcheck disable=SC2086
  set -- ${row}; b="$1"; t="$2"; v="$3"; band="$4"; vc0="$5"
  sumfile="${WORK}/s100settle_${b}_${t}_${v}.csv"
  cid="$(simenv_corner_id "${b}" "${t}" "${v}")"
  tag="f100_${b}_T${t}_V${v}_X${SIM_TSTOP}"; tag="$(simenv_mktag "${tag}")"
  simenv_archive_log "${WORK}" "${tag}" "${OUT}" "f100x_${cid}"

  # Row layout, from run.sh --one-lock's own printf (28 fields):
  #  1 bundle 2 temp 3 vdd 4 fout 5 band 6 trim 7 fref 8 N 9 vc0
  #  10 fout_meas 11 ffb 12 nmeas 13 ferr 14 phi_b 15 skew1 16 skew2 17 skew3
  #  18 wup1 19 wdn1 20 vctrl_avg 21 vctrl_min 22 vctrl_max 23 lock_lvl
  #  24 i_core 25 i_vco 26 i_div 27 tstop 28 tmax
  IFS=, read -r r_bundle r_temp r_vdd r_fout r_band r_trim r_fref r_n r_vc0 \
    r_foutm r_ffb r_nmeas r_ferr r_phib r_s1 r_s2 r_s3 r_wup r_wdn \
    r_vctrl_avg r_vmin r_vmax r_lock r_icore r_ivco r_idiv r_tstop r_tmax \
    <"${sumfile}"

  awk -v ferr="${r_ferr}" -v phib="${r_phib}" -v ta="${SIM_TA}" -v tb="${SIM_TB}" \
      -v bundle="${r_bundle}" -v temp="${r_temp}" -v vdd="${r_vdd}" \
      -v band="${r_band}" -v vc0="${r_vc0}" -v foutm="${r_foutm}" \
      -v ffb="${r_ffb}" -v nmeas="${r_nmeas}" -v vctrl_avg="${r_vctrl_avg}" \
      -v lock="${r_lock}" -v tstop="${r_tstop}" 'BEGIN {
    function s(x) { if (x ~ /[uU]$/) return x * 1e-6;
                    if (x ~ /[nN]$/) return x * 1e-9;
                    if (x ~ /[pP]$/) return x * 1e-12;
                    return x + 0 }
    win = s(tb) - s(ta);
    phia_ns = phib + ferr * win * 1e9;
    dphi_ns = phib - phia_ns;
    settled = (dphi_ns < 0 ? -dphi_ns : dphi_ns) > 0.1 ? "no" : "yes";
    over = (phib < 0 ? -phib : phib) > 1.0 ? "yes" : "no";
    printf "%s,%s,%s,%s,%s,%s,%s,%s,%s,%.6g,%s,%s,%.6g,%.6g,%s,%s,%s,%s,%s\n", \
      bundle, temp, vdd, band, vc0, foutm, ffb, nmeas, ferr, phib, \
      vctrl_avg, lock, phia_ns, dphi_ns, settled, over, tstop, ta, tb
  }' >>"${SUMMARY}"
done

echo
echo "static_phase_settling_campaign: summary ${SUMMARY}"
echo "static_phase_settling_campaign: netlist snapshot ${SNAPDIR}/${RID}.spice"
echo "static_phase_settling_campaign: sha256 $(simenv_sha256 "${SNAPDIR}/${RID}.spice")"
echo "${RID}" >"${OUT}/.record-id"
