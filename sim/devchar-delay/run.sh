#!/usr/bin/env bash
# gf180-pll :: devchar-delay :: corner runner
#
# Sweeps tb_delay_stage.sp over the full repo PVT grid:
#   process {typical, ff, ss, fs, sf} x temp {-40, 27, 125} C x supply
#   {2.97, 3.30, 3.63} V  = 45 points.
#
# Usage:
#   ./run.sh                 # full 45-point grid -> results/delay_corners.csv
#   ./run.sh --check         # nominal corner only, printed to stdout (no write)
#   SIM_JOBS=4 ./run.sh      # cap parallelism
#
# Results are append-only evidence: the CSV carries a provenance header naming
# the PDK hash, simulator version, model sections and netlist.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/simenv.sh
. "${HERE}/../lib/simenv.sh"

DECK="${HERE}/tb_delay_stage.sp"
WORK="${HERE}/work"
OUT="${HERE}/results/delay_corners.csv"

CSV_HEADER="process,temp_c,vdd_v,ring1x_fosc_hz,ring1x_tstage_s,ring1x_isupply_a,ring1x_qstage_c,ring1x_cstage_f,ring4x_fosc_hz,ring4x_tstage_s,ring4x_isupply_a,fo1_tphl_s,fo1_tplh_s,fo1_tpd_s,fo1_tfall_s,fo1_trise_s,idsat_n_1u_a,idsat_p_2u5_a"

# --------------------------------------------------------------------------
# Single corner point. Prints one CSV row on stdout.
# --------------------------------------------------------------------------
run_one() {
  local corner="$1" temp="$2" vdd="$3"
  local tag="${corner}_T${temp}_V${vdd}"
  tag="${tag//./p}"
  tag="${tag//-/m}"

  simenv_run_deck "${DECK}" "${WORK}" "${tag}" "${corner}" "${temp}" "vsup=${vdd}" >/dev/null
  local log="${WORK}/${tag}/ngspice.log"

  local r1_fosc r1_tstage r1_iavg r1_period r4_fosc r4_tstage r4_iavg
  local tphl tplh tpd tf tr idn idp
  r1_fosc=$(simenv_meas "${log}" r1_fosc)
  r1_tstage=$(simenv_meas "${log}" r1_tstage)
  r1_period=$(simenv_meas "${log}" r1_period)
  r1_iavg=$(simenv_meas "${log}" r1_iavg)
  r4_fosc=$(simenv_meas "${log}" r4_fosc)
  r4_tstage=$(simenv_meas "${log}" r4_tstage)
  r4_iavg=$(simenv_meas "${log}" r4_iavg)
  tphl=$(simenv_meas "${log}" ch_tphl)
  tplh=$(simenv_meas "${log}" ch_tplh)
  tpd=$(simenv_meas "${log}" ch_tpd)
  tf=$(simenv_meas "${log}" ch_tf)
  tr=$(simenv_meas "${log}" ch_tr)
  idn=$(simenv_meas "${log}" dc_idn)
  idp=$(simenv_meas "${log}" dc_idp)

  # Derived: charge drawn from the supply per stage transition, and the
  # equivalent switched capacitance C = Q/Vdd. Includes short-circuit current,
  # so it is an upper bound on the pure load capacitance -- which is the number
  # a ring-VCO power/frequency estimate actually wants.
  awk -v c="${corner}" -v t="${temp}" -v v="${vdd}" \
      -v r1f="${r1_fosc}" -v r1ts="${r1_tstage}" -v r1i="${r1_iavg}" -v r1p="${r1_period}" \
      -v r4f="${r4_fosc}" -v r4ts="${r4_tstage}" -v r4i="${r4_iavg}" \
      -v tphl="${tphl}" -v tplh="${tplh}" -v tpd="${tpd}" -v tf="${tf}" -v tr="${tr}" \
      -v idn="${idn}" -v idp="${idp}" '
    function abs(x) { return x < 0 ? -x : x }
    BEGIN {
      nstage = 5
      q = abs(r1i) * r1p / nstage
      cs = (v > 0) ? q / v : 0
      printf "%s,%s,%s,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g\n",
             c, t, v, r1f, r1ts, abs(r1i), q, cs, r4f, r4ts, abs(r4i),
             tphl, tplh, tpd, tf, tr, abs(idn), abs(idp)
    }'
}

# --------------------------------------------------------------------------
# Entry points
# --------------------------------------------------------------------------
if [ "${1:-}" = "--one" ]; then
  shift
  run_one "$@"
  exit 0
fi

simenv_require_tools

if [ "${1:-}" = "--check" ]; then
  echo "${CSV_HEADER}"
  run_one typical 27 3.30
  exit 0
fi

mkdir -p "${WORK}" "${HERE}/results"

# Build the job list, then fan out. Each job re-enters this script with --one.
JOBLIST="${WORK}/jobs.txt"
: >"${JOBLIST}"
for corner in "${SIMENV_MOS_CORNERS[@]}"; do
  for temp in "${SIMENV_TEMPS[@]}"; do
    for vdd in "${SIMENV_VDDS[@]}"; do
      echo "${corner} ${temp} ${vdd}" >>"${JOBLIST}"
    done
  done
done
NPOINTS=$(wc -l <"${JOBLIST}" | tr -d ' ')
echo "devchar-delay: ${NPOINTS} corner points, $(simenv_jobs) parallel jobs"

ROWS="${WORK}/rows.csv"
: >"${ROWS}"
# shellcheck disable=SC2016
xargs -P "$(simenv_jobs)" -L 1 \
  "${BASH:-/bin/bash}" -c 'exec "$0" --one "$@"' "${HERE}/run.sh" \
  <"${JOBLIST}" >>"${ROWS}"

EXPECTED=$((${#SIMENV_MOS_CORNERS[@]} * ${#SIMENV_TEMPS[@]} * ${#SIMENV_VDDS[@]}))
GOT=$(wc -l <"${ROWS}" | tr -d ' ')
if [ "${GOT}" -ne "${EXPECTED}" ]; then
  echo "ERROR: expected ${EXPECTED} corner rows, collected ${GOT}" >&2
  exit 1
fi

{
  simenv_provenance "devchar-delay" \
    "sim/devchar-delay/tb_delay_stage.sp" \
    "process{typical,ff,ss,fs,sf} x temp{-40,27,125}C x vdd{2.97,3.30,3.63}V = ${EXPECTED} points"
  cat <<'EOF'
# topology_ring: 5-stage self-loaded ring of minimum-length CMOS inverters
#   ring1x: Wn=1.0um Wp=2.5um L=0.28um ; ring4x: Wn=4.0um Wp=10.0um L=0.28um
#   tstage = 1/(2*N*fosc) with N=5 ; fosc from 8 periods after start-up
# topology_fo1: open 4-inverter chain (1x), stage 3 measured (identical driver
#   and identical fan-out-1 load), ideal step at the chain input
# idsat_n_1u / idsat_p_2u5: single device at Vgs=Vds=Vdd, W=1.0um n / 2.5um p
# qstage/cstage: supply charge per stage transition of ring1x and Q/Vdd;
#   includes short-circuit current, so cstage is an upper bound on load C
EOF
  echo "${CSV_HEADER}"
  sort -t, -k1,1 -k2,2n -k3,3n "${ROWS}"
} >"${OUT}"

echo "devchar-delay: wrote ${OUT}"
