#!/usr/bin/env bash
# gf180-pll :: vco-tuning-range :: open-loop f(Vctrl) / Kvco corner campaign
#
# Sweeps tb_vco_tuning.sp over
#   7 corner bundles x 3 temperatures x 3 supplies x 8 band codes = 504 runs,
# each run producing f and I at 7 control voltages (3528 (band, Vctrl, PVT)
# points in total).
#
# Corner bundles (expanded in the minted record):
#   typical, ff, ss, fs, sf   MOS-only; passives left at res_typical/moscap_typical
#   all-slow                  ss  + res_ss + moscap_ss
#   all-fast                  ff  + res_ff + moscap_ff
# The two composite bundles exist because this DUT's frequency is set by a poly
# resistor (the V->I degeneration and the constant-gm reference), so a MOS-only
# sweep would leave the single most Kvco-relevant process axis at typical.
#
# Usage:
#   ./run.sh                 # full campaign -> mints a records/<id>.md
#   ./run.sh --check         # nominal corner, band 0 and 7 only, to stdout
#   SIM_JOBS=8 ./run.sh      # cap parallelism

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP="$(cd "${HERE}/.." && pwd)"
REPO="$(cd "${EXP}/../.." && pwd)"
# shellcheck source=../../lib/simenv.sh
. "${HERE}/../../lib/simenv.sh"

DECK="${HERE}/tb_vco_tuning.sp"
DUT="${REPO}/design/netlist/vco.spice"
WORK="${EXP}/work"

BUNDLES=(typical ff ss fs sf all-slow all-fast)
BANDS=(0 1 2 3 4 5 6 7)
VCTRLS=(0.9 1.2 1.5 1.8 2.1 2.4 2.7)

CSV_HEADER="bundle,temp_c,vdd_v,band,vctrl_v,fosc_hz,isupply_a"

# Map a bundle name to the .lib sections it stands for.
bundle_libs() {
  case "$1" in
    all-slow) echo "ss,res_ss,moscap_ss" ;;
    all-fast) echo "ff,res_ff,moscap_ff" ;;
    *)        echo "$1,res_typical,moscap_typical" ;;
  esac
}

# Frequency estimate used only to size the transient window (never to produce a
# result). Calibrated against the nominal corner; the corner factors bound the
# measured spread with margin, and a failed .meas triggers a retry with a longer
# window, so an inaccurate estimate costs runtime, never correctness.
f_est() { # <band> <vctrl> <bundle> <temp> <vdd>
  python3 - "$@" <<'PY'
import sys
band, vctrl, bundle, temp, vdd = int(sys.argv[1]), float(sys.argv[2]), sys.argv[3], float(sys.argv[4]), float(sys.argv[5])
ftemp = {-40.0: 0.75, 27.0: 1.0, 125.0: 1.35}[temp]
fres  = {"all-fast": 1.25, "all-slow": 0.80}.get(bundle, 1.0)
fvdd  = 1.0 + (3.30 - vdd) * 0.36
print("%.6g" % (4.5e6 * (1.65 ** band) * (1 + (vctrl - 0.9) / 1.33) * ftemp * fres * fvdd))
PY
}

# --------------------------------------------------------------------------
# One (bundle, temp, vdd, band) point -> seven CSV rows on stdout.
# --------------------------------------------------------------------------
run_one() {
  local bundle="$1" temp="$2" vdd="$3" band="$4"
  local b0=$((band & 1)) b1=$(((band >> 1) & 1)) b2=$(((band >> 2) & 1))
  local tag="${bundle}_T${temp}_V${vdd}_B${band}"
  tag="${tag//./p}"; tag="${tag//-/m}"

  local flo fhi
  flo=$(f_est "${band}" 0.9 "${bundle}" "${temp}" "${vdd}")
  fhi=$(f_est "${band}" 2.7 "${bundle}" "${temp}" "${vdd}")

  local rundir="${WORK}/${tag}"
  mkdir -p "${rundir}"
  cp "${WORK}/vco.spice" "${rundir}/vco.spice"

  local libs attempt=0 stretch=1 ok=0
  libs=$(bundle_libs "${bundle}")

  while [ "${attempt}" -lt 3 ]; do
    local tsettle tstop tmax
    read -r tsettle tstop tmax < <(python3 -c "
flo=${flo}; fhi=${fhi}; s=${stretch}
ts=4.0/flo*s; print('%.6g %.6g %.6g' % (ts, ts + 7.0/flo*s, 1.0/(80*fhi)))")
    if simenv_run_deck "${DECK}" "${WORK}" "${tag}" "${libs}" "${temp}" \
        "vsup=${vdd}" "b0v=${b0}*${vdd}" "b1v=${b1}*${vdd}" "b2v=${b2}*${vdd}" \
        "tsettle=${tsettle}" "tstop=${tstop}" "tstep=${tmax}" "tmax=${tmax}" >/dev/null 2>&1
    then
      # every one of the seven frequency measurements must have landed
      local ngood
      ngood=$(grep -cE "^ *f[1-7] *=" "${rundir}/ngspice.log" || true)
      [ "${ngood}" -eq 7 ] && { ok=1; break; }
    fi
    attempt=$((attempt + 1))
    stretch=$((stretch * 3))
  done

  if [ "${ok}" -ne 1 ]; then
    echo "ERROR: ${tag} did not converge to 7 valid measurements" >&2
    return 1
  fi

  local log="${rundir}/ngspice.log"
  local i
  for i in 1 2 3 4 5 6 7; do
    local f cur
    f=$(simenv_meas "${log}" "f${i}")
    cur=$(simenv_meas "${log}" "i${i}")
    awk -v b="${bundle}" -v t="${temp}" -v v="${vdd}" -v bd="${band}" \
        -v vc="${VCTRLS[$((i - 1))]}" -v f="${f}" -v c="${cur}" \
        'function abs(x){return x<0?-x:x} BEGIN{printf "%s,%s,%s,%s,%s,%.7g,%.6g\n", b,t,v,bd,vc,f,abs(c)}'
  done
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
[ -f "${DUT}" ] || { echo "ERROR: ${DUT} missing -- run design/netlist.sh" >&2; exit 1; }

mkdir -p "${WORK}"
cp "${DUT}" "${WORK}/vco.spice"

if [ "${1:-}" = "--check" ]; then
  echo "${CSV_HEADER}"
  run_one typical 27 3.30 0
  run_one typical 27 3.30 7
  exit 0
fi

JOBLIST="${WORK}/jobs.txt"
: >"${JOBLIST}"
for bundle in "${BUNDLES[@]}"; do
  for temp in "${SIMENV_TEMPS[@]}"; do
    for vdd in "${SIMENV_VDDS[@]}"; do
      for band in "${BANDS[@]}"; do
        echo "${bundle} ${temp} ${vdd} ${band}" >>"${JOBLIST}"
      done
    done
  done
done
NPOINTS=$(wc -l <"${JOBLIST}" | tr -d ' ')
echo "vco-tuning-range: ${NPOINTS} (corner, band) runs x ${#VCTRLS[@]} control points, $(simenv_jobs) parallel jobs"

ROWS="${WORK}/rows.csv"
: >"${ROWS}"
# shellcheck disable=SC2016
xargs -P "$(simenv_jobs)" -L 1 \
  "${BASH:-/bin/bash}" -c 'exec "$0" --one "$@"' "${HERE}/run.sh" \
  <"${JOBLIST}" >>"${ROWS}"

EXPECTED=$((NPOINTS * ${#VCTRLS[@]}))
GOT=$(wc -l <"${ROWS}" | tr -d ' ')
if [ "${GOT}" -ne "${EXPECTED}" ]; then
  echo "ERROR: expected ${EXPECTED} rows, collected ${GOT}" >&2
  exit 1
fi

# --------------------------------------------------------------------------
# Freeze the evidence (sim/README.md convention).
# --------------------------------------------------------------------------
RID=$(simenv_record_id)
SNAPDIR="${EXP}/netlist-snapshots"
CORNERSDIR="${EXP}/corners/${RID}"
RECORDSDIR="${EXP}/records"
mkdir -p "${SNAPDIR}" "${CORNERSDIR}" "${RECORDSDIR}"

cp "${DUT}" "${SNAPDIR}/${RID}.spice"
SHA=$(simenv_sha256 "${SNAPDIR}/${RID}.spice")

# One committed log per PVT point, holding that point's eight band runs back to
# back (sim/README.md's corner-id naming is per PVT point; band code is an inner
# axis of this campaign).
for bundle in "${BUNDLES[@]}"; do
  for temp in "${SIMENV_TEMPS[@]}"; do
    for vdd in "${SIMENV_VDDS[@]}"; do
      cid=$(simenv_corner_id "${bundle}" "${temp}" "${vdd}")
      : >"${CORNERSDIR}/${cid}.log"
      for band in "${BANDS[@]}"; do
        tag="${bundle}_T${temp}_V${vdd}_B${band}"
        tag="${tag//./p}"; tag="${tag//-/m}"
        {
          echo "======== band ${band} :: generated deck (${cid}) ========"
          cat "${WORK}/${tag}/deck.sp"
          echo
          echo "======== band ${band} :: ngspice output ========"
          cat "${WORK}/${tag}/ngspice.log"
          echo
        } >>"${CORNERSDIR}/${cid}.log"
      done
    done
  done
done

CSV_OUT="${CORNERSDIR}/vco_tuning.csv"
CORNER_DESC="7 bundles{typical,ff,ss,fs,sf,all-slow,all-fast} x temp{-40,27,125}C x vdd{2.97,3.30,3.63}V x band{0..7} x vctrl{0.9..2.7 in 0.3V} = ${EXPECTED} points"
{
  simenv_provenance "vco-tuning-range" "${RID}" \
    "design/vco.sch -> sim/vco-tuning-range/netlist-snapshots/${RID}.spice" "${CORNER_DESC}"
  cat <<'EOF'
# dut: 5-stage current-starved single-ended CMOS ring VCO (DR-001 Decision 2),
#   3-bit band select via three cascaded switched-ratio mirror stages
#   (x1.65 / x1.65^2 / x1.65^4), fine control by a source-degenerated V->I
#   converter offset by a 2*Vgs reference so I_sum ~ (Vctrl + Voff)/Rdeg.
#   See spec/decision-records/DR-003 for the band-mapping decision.
# fosc_hz: measured at the buffered output CLK over 4 whole cycles after tsettle
# isupply_a: average current out of that instance's own VDD_VCO ammeter over
#   the measurement window (whole block: bias + ring + output buffer + decap)
# bundles: typical/ff/ss/fs/sf are MOS-only (res_typical, moscap_typical);
#   all-slow = ss+res_ss+moscap_ss ; all-fast = ff+res_ff+moscap_ff
EOF
  echo "${CSV_HEADER}"
  sort -t, -k1,1 -k2,2n -k3,3n -k4,4n -k5,5n "${ROWS}"
} >"${CSV_OUT}"

echo "vco-tuning-range: wrote ${CSV_OUT}"
echo "vco-tuning-range: wrote ${CORNERSDIR}/ (per-PVT-point logs)"
echo "vco-tuning-range: record id ${RID}"
echo "vco-tuning-range: netlist sha256 ${SHA}"
echo "${RID}" >"${WORK}/last_record_id"
