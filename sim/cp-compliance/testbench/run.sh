#!/usr/bin/env bash
# gf180-pll :: cp-compliance :: corner runner for the charge pump's output
# compliance range, UP/DN mismatch, and 2-bit Icp trim.
#
# SUPERSEDED FOR NEW RUNS by this campaign's sim/harness manifests --
#   python3 sim/run_corners.py cp-compliance                    # DC bench
#   python3 sim/run_corners.py sim/cp-compliance/testbench-switch  # switching bench
# instead (testbench/tb.json + tb_cp_dc.spice for the former,
# testbench-switch/tb.json + tb_cp_switch.spice for the latter -- the harness
# mints one record per manifest, so this script's single combined record is
# now two sibling records). This script is kept because the records it
# already minted are append-only evidence and it is the only thing that can
# regenerate the extra CSV artifacts they cite (cp_curves.csv in particular,
# which the harness migration does not reproduce -- see the DC manifest's
# Methodology); do not extend it.
#
# Two testbenches, one record (they substantiate one claim -- "the charge pump
# holds both current sources in saturation across the Vctrl window, and here is
# how far apart the two polarities are"):
#
#   tb_cp_dc.sp      DC output characteristic of both polarities over the whole
#                    0..3.63 V output range, at all 45 PVT corners x all 4 Icp
#                    trim codes.  Yields the compliance range, the DC UP/DN
#                    current mismatch across the ~0.9-2.4 V Vctrl window, the
#                    trim range/step, and a direct |vds|-|vdsat| saturation
#                    margin for the output devices at both ends of the window.
#   tb_cp_switch.sp  Transient switching of each polarity from the same control
#                    edge, at all 45 PVT corners x three control-node voltages.
#                    Yields the turn-on/turn-off delays and the effective
#                    UP/DN pulse-width skew -- the timing half of the mismatch
#                    budget, which a DC sweep cannot see.
#
# Usage:
#   ./run.sh                 # full grid -> mints a records/<id>.md
#   ./run.sh --check         # nominal corner only, both benches, to stdout
#   SIM_JOBS=4 ./run.sh      # cap parallelism

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP="$(cd "${HERE}/.." && pwd)"
REPO="$(cd "${EXP}/../.." && pwd)"
# shellcheck source=../../lib/simenv.sh
. "${HERE}/../../lib/simenv.sh"

DECK_DC="${HERE}/tb_cp_dc.sp"
DECK_SW="${HERE}/tb_cp_switch.sp"
WORK="${EXP}/work"
NETLIST="${WORK}/dut.spice"

# Vctrl window under test (DR-001 Decision 2 design intent, ~0.9-2.4 V of the
# 3.3 V rail).  VLO/VHI are the window edges the compliance verdict is taken
# at; VMID is the nominal operating point.
VLO=0.9
VMID=1.65
VHI=2.4

# The four 2-bit trim codes, as "b1 b0" (Icp = Iunit * (1 + b0 + 2*b1)).
TRIM_CODES=("0 0" "0 1" "1 0" "1 1")
# Nominal code used for the transient sweep and for the headline numbers.
NOM_B1=1
NOM_B0=0

DC_HEADER="process,temp_c,vdd_v,b1,b0,units,iup_lo_a,idn_lo_a,iup_mid_a,idn_mid_a,iup_hi_a,idn_hi_a,mism_lo_pct,mism_mid_pct,mism_hi_pct,mism_absmax_pct,iup_flat_pct,idn_flat_pct,satcasc_lo_v,satcasc_lo_dev,satcasc_hi_v,satcasc_hi_dev,satmir_lo_v,satmir_hi_v"
SW_HEADER="process,temp_c,vdd_v,vctrl_v,iup_ss_a,idn_ss_a,qup_c,qdn_c,wup_s,wdn_s,wskew_s,ton_up_s,ton_dn_s,toff_up_s,toff_dn_s"
CURVES_HEADER="process,temp_c,vdd_v,b1,b0,vout_v,iup_a,idn_a"

# Decimation of the committed curve file: the sweep runs at 20 mV, the archived
# curve keeps every 5th point (100 mV), which still resolves both knees.
CURVE_DECIMATE=5

# --------------------------------------------------------------------------
# Place the xschem export next to the generated deck: the decks `.include`
# "dut.spice" relative to their run directory, and `.include` takes no
# parameter substitution.
# --------------------------------------------------------------------------
stage_netlist() {
  mkdir -p "$1"
  cp "${NETLIST}" "$1/dut.spice"
}

# --------------------------------------------------------------------------
# One DC point: run_dc <corner> <temp> <vdd> <b1> <b0> <summary-out> <curves-out>
# --------------------------------------------------------------------------
run_dc() {
  local corner="$1" temp="$2" vdd="$3" b1="$4" b0="$5" sfile="$6" cfile="$7"
  local tag="dc_${corner}_T${temp}_V${vdd}_C${b1}${b0}"
  tag="${tag//./p}"; tag="${tag//-/m}"

  stage_netlist "${WORK}/${tag}"
  simenv_run_deck "${DECK_DC}" "${WORK}" "${tag}" "${corner}" "${temp}" \
    "vsup=${vdd}" "b0_code=${b0}" "b1_code=${b1}" >/dev/null
  local rundir="${WORK}/${tag}"

  local satlo sathi
  satlo=$(grep "^SATLO " "${rundir}/ngspice.log" | tail -1)
  sathi=$(grep "^SATHI " "${rundir}/ngspice.log" | tail -1)
  if [ -z "${satlo}" ] || [ -z "${sathi}" ]; then
    echo "ERROR: missing saturation operating point for tag=${tag}" >&2
    return 1
  fi

  awk -v corner="${corner}" -v temp="${temp}" -v vdd="${vdd}" \
      -v b1="${b1}" -v b0="${b0}" -v vlo="${VLO}" -v vmid="${VMID}" -v vhi="${VHI}" \
      -v satlo="${satlo}" -v sathi="${sathi}" -v dec="${CURVE_DECIMATE}" \
      -v sfile="${sfile}" -v cfile="${cfile}" '
    function abs(x) { return x < 0 ? -x : x }
    function at(target,   k) { k = int((target - v[1]) / dv + 0.5) + 1; if (k < 1) k = 1; if (k > n) k = n; return k }
    # Minimum |vds|-|vdsat| over the devices in one SAT record whose name
    # matches `want`, and the name of the device that owns it.  Negative means
    # that device has left saturation at that output voltage.
    #
    # The verdict is taken over the CASCODE devices only (want = "casc").  The
    # bottom mirror devices (nbot/ptop) are reported separately, because a
    # wide-swing cascode bias deliberately parks them AT the saturation
    # boundary -- that is the whole point of the wide-swing bias, and their
    # operating point is set by the mirror, not by the output voltage, so a
    # margin of about zero there is the design working as intended, not a
    # compliance failure.
    function satmin(rec, want, out,   f, i, m, name, vds, vdsat, best, bestname) {
      split(rec, f, " ")
      best = 1e9
      for (i = 2; i < length(f); i += 4) {
        name = f[i]; sub(/_vds$/, "", name)
        if (name !~ want) continue
        vds = f[i + 1] + 0; vdsat = f[i + 3] + 0
        m = abs(vds) - abs(vdsat)
        if (m < best) { best = m; bestname = name }
      }
      out[1] = best; out[2] = bestname
    }
    { n++; v[n] = $1; iup[n] = $2; idn[n] = $4 }
    END {
      if (n < 10) { print "ERROR: short sweep" > "/dev/stderr"; exit 1 }
      dv = (v[n] - v[1]) / (n - 1)
      klo = at(vlo); kmid = at(vmid); khi = at(vhi)

      # Flatness of each polarity across the Vctrl window, as a percentage of
      # its mid-window value: this is the compliance evidence in current terms.
      upmin = 1e9; upmax = -1e9; dnmin = 1e9; dnmax = -1e9; mmax = 0
      for (k = klo; k <= khi; k++) {
        if (iup[k] < upmin) upmin = iup[k]; if (iup[k] > upmax) upmax = iup[k]
        if (idn[k] < dnmin) dnmin = idn[k]; if (idn[k] > dnmax) dnmax = idn[k]
        mm = 100 * (iup[k] - idn[k]) / (0.5 * (iup[k] + idn[k]))
        if (abs(mm) > abs(mmax)) mmax = mm
      }

      satmin(satlo, "casc", a); satmin(sathi, "casc", b)
      satmin(satlo, "bot|top", c); satmin(sathi, "bot|top", d)

      printf "%s,%s,%s,%s,%s,%d,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%s,%.4f,%s,%.4f,%.4f\n",
             corner, temp, vdd, b1, b0, 1 + b0 + 2 * b1,
             iup[klo], idn[klo], iup[kmid], idn[kmid], iup[khi], idn[khi],
             100 * (iup[klo] - idn[klo]) / (0.5 * (iup[klo] + idn[klo])),
             100 * (iup[kmid] - idn[kmid]) / (0.5 * (iup[kmid] + idn[kmid])),
             100 * (iup[khi] - idn[khi]) / (0.5 * (iup[khi] + idn[khi])),
             mmax,
             100 * (upmax - upmin) / iup[kmid], 100 * (dnmax - dnmin) / idn[kmid],
             a[1], a[2], b[1], b[2], c[1], d[1] >> sfile

      for (k = 1; k <= n; k += dec)
        printf "%s,%s,%s,%s,%s,%.4f,%.6g,%.6g\n",
               corner, temp, vdd, b1, b0, v[k], iup[k], idn[k] >> cfile
    }' "${rundir}/iv_cp.dat"
}

# --------------------------------------------------------------------------
# One switching point: run_sw <corner> <temp> <vdd> <vctrl> <summary-out>
# --------------------------------------------------------------------------
run_sw() {
  local corner="$1" temp="$2" vdd="$3" vctrl="$4" sfile="$5"
  local tag="sw_${corner}_T${temp}_V${vdd}_X${vctrl}"
  tag="${tag//./p}"; tag="${tag//-/m}"

  stage_netlist "${WORK}/${tag}"
  simenv_run_deck "${DECK_SW}" "${WORK}" "${tag}" "${corner}" "${temp}" \
    "vsup=${vdd}" "vctrl=${vctrl}" "b0_code=${NOM_B0}" "b1_code=${NOM_B1}" >/dev/null
  local rundir="${WORK}/${tag}"

  local line
  line=$(grep "^CPSW " "${rundir}/ngspice.log" | tail -1)
  [ -n "${line}" ] || { echo "ERROR: missing CPSW for tag=${tag}" >&2; return 1; }
  f() { echo "${line}" | sed -n "s/.*$1=\([^ ]*\).*/\1/p"; }
  printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n' \
    "${corner}" "${temp}" "${vdd}" "${vctrl}" \
    "$(f iup_ss)" "$(f idn_ss)" "$(f qup)" "$(f qdn)" "$(f wup)" "$(f wdn)" \
    "$(f wskew)" "$(f ton_up)" "$(f ton_dn)" "$(f toff_up)" "$(f toff_dn)" >>"${sfile}"
}

# --------------------------------------------------------------------------
# Entry points
# --------------------------------------------------------------------------
case "${1:-}" in
  --one-dc) shift; run_dc "$@"; exit 0 ;;
  --one-sw) shift; run_sw "$@"; exit 0 ;;
esac

# --------------------------------------------------------------------------
# Supersession (sim/README.md :: Status / supersession language).
#
# A record's **Supersedes** field is the ONLY pointer between an old record and
# the one that replaces it -- the superseded record's bytes never change.  So
# the field has to be settable at mint time rather than edited in afterwards,
# which would itself be a rewrite of a record.
#
#   SIM_SUPERSEDES=<record-id>        the record this run replaces
#   SIM_SUPERSEDES_NOTE=<one line>    why, e.g. "netlist provenance only"
#
# Two further knobs exist for the same reason -- a record's text is fixed at
# mint time and can never be edited afterwards, so anything that has to be
# TRUE OF THIS RUN rather than of the campaign has to be settable from outside:
#
#   SIM_AUTHOR=<who>                  attribution, when a later issue re-runs
#                                     this campaign against a changed design
#   SIM_METHOD_NOTE=<text>            one extra Methodology bullet, e.g. which
#                                     design revision this run measured and what
#                                     it is comparable to
#
# Unset, both fall back to the wording this campaign was minted with, so an
# unqualified re-run emits exactly what it emitted before.
#
# Unset, the record says it is the first for its claim, exactly as before.
# --------------------------------------------------------------------------
supersedes_field() {
  if [ -z "${SIM_SUPERSEDES:-}" ]; then
    echo "- **Supersedes**: (none -- first record for this claim)"
  elif [ -z "${SIM_SUPERSEDES_NOTE:-}" ]; then
    echo "- **Supersedes**: ${SIM_SUPERSEDES}"
  else
    echo "- **Supersedes**: ${SIM_SUPERSEDES} -- ${SIM_SUPERSEDES_NOTE}"
  fi
}

author_field() {
  echo "- **Timestamp / author**: $(date -u +%Y-%m-%dT%H:%M:%SZ), ${SIM_AUTHOR:-agent-builder (issue #9)}"
}

# Emits with a LEADING newline and none trailing, so it is appended to the end
# of the last Methodology bullet: command substitution strips trailing newlines,
# so a trailing-newline form would run the next field onto the same line.
method_note() {
  [ -n "${SIM_METHOD_NOTE:-}" ] && printf '\n  - %s' "${SIM_METHOD_NOTE}"
  return 0
}

simenv_require_tools
mkdir -p "${WORK}"

echo "cp-compliance: exporting design/ via xschem ..."
"${REPO}/design/netlist.sh" --top pfd_cp "${WORK}" >/dev/null
[ -f "${NETLIST}" ] || { echo "ERROR: ${NETLIST} not produced" >&2; exit 1; }

if [ "${1:-}" = "--check" ]; then
  tmpdir=$(mktemp -d)
  trap 'rm -rf "${tmpdir}"' EXIT
  run_dc typical 27 3.30 "${NOM_B1}" "${NOM_B0}" "${tmpdir}/dc.csv" "${tmpdir}/cur.csv"
  run_sw typical 27 3.30 "${VMID}" "${tmpdir}/sw.csv"
  echo "${DC_HEADER}"; cat "${tmpdir}/dc.csv"
  echo "${SW_HEADER}"; cat "${tmpdir}/sw.csv"
  exit 0
fi

DCJOBS="${WORK}/jobs_dc.txt"; : >"${DCJOBS}"
SWJOBS="${WORK}/jobs_sw.txt"; : >"${SWJOBS}"
for corner in "${SIMENV_MOS_CORNERS[@]}"; do
  for temp in "${SIMENV_TEMPS[@]}"; do
    for vdd in "${SIMENV_VDDS[@]}"; do
      for code in "${TRIM_CODES[@]}"; do
        set -- ${code}
        tag="dc_${corner}_T${temp}_V${vdd}_C$1$2"; tag="${tag//./p}"; tag="${tag//-/m}"
        echo "${corner} ${temp} ${vdd} $1 $2 ${WORK}/${tag}.sum ${WORK}/${tag}.cur" >>"${DCJOBS}"
      done
      for vctrl in "${VLO}" "${VMID}" "${VHI}"; do
        tag="sw_${corner}_T${temp}_V${vdd}_X${vctrl}"; tag="${tag//./p}"; tag="${tag//-/m}"
        echo "${corner} ${temp} ${vdd} ${vctrl} ${WORK}/${tag}.sum" >>"${SWJOBS}"
      done
    done
  done
done
NDC=$(wc -l <"${DCJOBS}" | tr -d ' ')
NSW=$(wc -l <"${SWJOBS}" | tr -d ' ')
NCORNERS=$(( NDC / ${#TRIM_CODES[@]} ))
echo "cp-compliance: ${NCORNERS} PVT corners; ${NDC} DC runs (x4 trim codes) + ${NSW} switching runs (x3 Vctrl), $(simenv_jobs) parallel jobs"

rm -f "${WORK}"/*.sum "${WORK}"/*.cur
# shellcheck disable=SC2016
xargs -P "$(simenv_jobs)" -L 1 \
  "${BASH:-/bin/bash}" -c 'exec "$0" --one-dc "$@"' "${HERE}/run.sh" <"${DCJOBS}"
# shellcheck disable=SC2016
xargs -P "$(simenv_jobs)" -L 1 \
  "${BASH:-/bin/bash}" -c 'exec "$0" --one-sw "$@"' "${HERE}/run.sh" <"${SWJOBS}"

GOT=$(cat "${WORK}"/*.sum | wc -l | tr -d ' ')
if [ "${GOT}" -ne "$(( NDC + NSW ))" ]; then
  echo "ERROR: expected $(( NDC + NSW )) summary rows, collected ${GOT}" >&2
  exit 1
fi

CORNER_DESC="process{typical,ff,ss,fs,sf} x temp{-40,27,125}C x vdd{2.97,3.30,3.63}V = ${NCORNERS} PVT points; DC bench run at all 4 Icp trim codes (${NDC} runs), switching bench run at Vctrl {${VLO}, ${VMID}, ${VHI}} V at the nominal trim code (${NSW} runs)"

# --------------------------------------------------------------------------
# Mint the evidence record (sim/README.md convention).
# --------------------------------------------------------------------------
RID=$(simenv_record_id)
SNAPDIR="${EXP}/netlist-snapshots"
CORNERSDIR="${EXP}/corners/${RID}"
RECORDSDIR="${EXP}/records"
mkdir -p "${SNAPDIR}" "${CORNERSDIR}" "${RECORDSDIR}"

cp "${NETLIST}" "${SNAPDIR}/${RID}.spice"
SHA=$(simenv_sha256 "${SNAPDIR}/${RID}.spice")

while read -r corner temp vdd b1 b0 _rest; do
  tag="dc_${corner}_T${temp}_V${vdd}_C${b1}${b0}"; tag="${tag//./p}"; tag="${tag//-/m}"
  cid="dc_$(simenv_corner_id "${corner}" "${temp}" "${vdd}")_code${b1}${b0}"
  simenv_archive_log "${WORK}" "${tag}" "${CORNERSDIR}" "${cid}"
done <"${DCJOBS}"
while read -r corner temp vdd vctrl _rest; do
  tag="sw_${corner}_T${temp}_V${vdd}_X${vctrl}"; tag="${tag//./p}"; tag="${tag//-/m}"
  cid="sw_$(simenv_corner_id "${corner}" "${temp}" "${vdd}")_vctrl${vctrl}"
  simenv_archive_log "${WORK}" "${tag}" "${CORNERSDIR}" "${cid}"
done <"${SWJOBS}"

OUT_DC="${CORNERSDIR}/cp_dc.csv"
OUT_SW="${CORNERSDIR}/cp_switch.csv"
OUT_CURVES="${CORNERSDIR}/cp_curves.csv"

{
  simenv_provenance "cp-compliance (DC)" "${RID}" "design/cp.sch (xschem export)" "${CORNER_DESC}"
  cat <<EOF
# Vctrl window under test: ${VLO} .. ${VHI} V, nominal ${VMID} V (DR-001 Decision 2)
# units: Icp in unit legs = 1 + b0 + 2*b1
# iup_*/idn_*: UP (source) and DN (sink) output current at the window's low,
#   mid and high point (A)
# mism_*_pct: 100*(iup-idn)/mean at that point; mism_absmax_pct is the largest
#   magnitude anywhere inside the window
# iup_flat_pct/idn_flat_pct: peak-to-peak variation of each polarity's current
#   across the window, as a percentage of its mid-window value
# satcasc_lo_v/satcasc_hi_v: smallest |vds|-|vdsat| among the two output
#   CASCODE devices at the low/high end of the window, with the device that
#   owns it.  Positive = in saturation.  This is the compliance verdict: the
#   cascode is the device whose operating point the output voltage moves.
# satmir_lo_v/satmir_hi_v: the same quantity for the two bottom MIRROR devices,
#   reported for context only.  A wide-swing cascode bias parks those at the
#   saturation boundary by construction (that is what buys the headroom), and
#   their bias does not move with the output voltage, so a margin near zero
#   there is the design working as intended.
EOF
  echo "${DC_HEADER}"
  cat "${WORK}"/dc_*.sum | sort -t, -k1,1 -k2,2n -k3,3n -k4,4 -k5,5
} >"${OUT_DC}"

{
  simenv_provenance "cp-compliance (switching)" "${RID}" "design/cp.sch (xschem export)" "${CORNER_DESC}"
  cat <<EOF
# Both polarities driven from the SAME control edge, one instance each, at the
# nominal trim code (b1 b0 = ${NOM_B1} ${NOM_B0}).
# iup_ss/idn_ss: steady-state current late in the 5 ns control pulse (A)
# qup/qdn: charge delivered over the switching event, including the tail-node
#   charge-sharing transient (C).  Sign convention: qup > 0 (sourced into the
#   control node), qdn < 0 (sunk out of it).
# wup/wdn: effective pulse width each polarity presents to the loop, q/i_ss (s)
# wskew: wup - wdn, the effective UP/DN TIMING mismatch (s) -- the quantity
#   that turns charge-pump asymmetry into static phase error
# ton_*/toff_*: 50%-of-i_ss crossing referenced to the 50% control edge (s)
EOF
  echo "${SW_HEADER}"
  cat "${WORK}"/sw_*.sum | sort -t, -k1,1 -k2,2n -k3,3n -k4,4n
} >"${OUT_SW}"

{
  simenv_provenance "cp-compliance (output I-V curves)" "${RID}" "design/cp.sch (xschem export)" "${CORNER_DESC}"
  cat <<'EOF'
# Complete output characteristic of both polarities at every corner and trim
# code, decimated from the 20 mV simulation grid to 100 mV.
EOF
  echo "${CURVES_HEADER}"
  cat "${WORK}"/dc_*.cur | sort -t, -k1,1 -k2,2n -k3,3n -k4,4 -k5,5 -k6,6n
} >"${OUT_CURVES}"

# --------------------------------------------------------------------------
# Headline statistics, computed from the just-written CSVs so the record text
# cannot drift from the data.
# --------------------------------------------------------------------------
DC_STATS=$(grep -v '^#' "${OUT_DC}" | tail -n +2 | awk -F, -v nb1="${NOM_B1}" -v nb0="${NOM_B0}" '
  function abs(x) { return x < 0 ? -x : x }
  {
    units = $6
    icp = 0.5 * ($9 + $10)                       # mean of UP/DN at mid window
    if (!(units in icpmin) || icp < icpmin[units]) icpmin[units] = icp
    if (!(units in icpmax) || icp > icpmax[units]) icpmax[units] = icp
    if (abs($16) > abs(mmax_all)) { mmax_all = $16; mmax_all_k = $1 "/" $2 "C/" $3 "V code" $4 $5 }
    if ($4 == nb1 && $5 == nb0) {
      if (abs($16) > abs(mmax_nom)) { mmax_nom = $16; mmax_nom_k = $1 "/" $2 "C/" $3 "V" }
      if (!seen_nom || $9 < icpmin_nom) icpmin_nom = $9
      if (!seen_nom || $9 > icpmax_nom) icpmax_nom = $9
      seen_nom = 1
      if ($17 > flatmax) { flatmax = $17; flatmax_k = $1 "/" $2 "C/" $3 "V (UP)" }
      if ($18 > flatmax) { flatmax = $18; flatmax_k = $1 "/" $2 "C/" $3 "V (DN)" }
    }
    if (!nsm || $19 < smlo) { smlo = $19; smlo_k = $1 "/" $2 "C/" $3 "V code" $4 $5 " " $20 }
    if (!nsm || $21 < smhi) { smhi = $21; smhi_k = $1 "/" $2 "C/" $3 "V code" $4 $5 " " $22 }
    if (!nsm || $23 < smrlo) smrlo = $23
    if (!nsm || $24 < smrhi) smrhi = $24
    nsm = 1
    if ($19 <= 0 || $21 <= 0) { nsat_fail++; satfails = satfails "\n  " $1 "/" $2 "C/" $3 "V code" $4 $5 ": lo=" $19 " (" $20 ") hi=" $21 " (" $22 ")" }
    nrows++
  }
  END {
    printf "DCROWS %d\n", nrows
    for (u = 1; u <= 4; u++) if (u in icpmin) printf "TRIM %d %.6g %.6g\n", u, icpmin[u], icpmax[u]
    printf "DCSUM mism_absmax_all=%.4f mism_absmax_all_at=%s mism_absmax_nom=%.4f mism_absmax_nom_at=%s flat_max_nom=%.4f flat_max_nom_at=%s satmarg_lo_min=%.4f satmarg_lo_at=%s satmarg_hi_min=%.4f satmarg_hi_at=%s satmir_lo_min=%.4f satmir_hi_min=%.4f nsat_fail=%d\n", mmax_all, mmax_all_k, mmax_nom, mmax_nom_k, flatmax, flatmax_k, smlo, smlo_k, smhi, smhi_k, smrlo, smrhi, nsat_fail + 0
    if (nsat_fail > 0) printf "SATFAILS:%s\n", satfails; else printf "SATFAILS: none\n"
  }')

SW_STATS=$(grep -v '^#' "${OUT_SW}" | tail -n +2 | awk -F, '
  function abs(x) { return x < 0 ? -x : x }
  {
    if (abs($11) > abs(wsk)) { wsk = $11; wsk_k = $1 "/" $2 "C/" $3 "V @Vctrl=" $4 }
    if (!n || $12 < tonup_min) tonup_min = $12
    if (!n || $12 > tonup_max) tonup_max = $12
    if (!n || $13 < tondn_min) tondn_min = $13
    if (!n || $13 > tondn_max) tondn_max = $13
    d = $12 - $13
    if (abs(d) > abs(tskew)) { tskew = d; tskew_k = $1 "/" $2 "C/" $3 "V @Vctrl=" $4 }
    n++
  }
  END {
    printf "SWSUM n=%d wskew_absmax=%.6g wskew_at=%s ton_up_min=%.6g ton_up_max=%.6g ton_dn_min=%.6g ton_dn_max=%.6g ton_skew_absmax=%.6g ton_skew_at=%s\n", n, wsk, wsk_k, tonup_min, tonup_max, tondn_min, tondn_max, tskew, tskew_k
  }')

echo "${DC_STATS}" | grep -E '^DCSUM|^SATFAILS|^TRIM'
echo "${SW_STATS}"

# The leading-space anchor is load-bearing: an unanchored `grep -o "n=..."`
# also matches the "n=" inside keys like `ton_up_min=`, which would silently
# turn a scalar into several lines of record text.
dcget() { echo "${DC_STATS}" | grep '^DCSUM' | grep -oE "(^| )$1=[^ ]*" | tr -d ' ' | cut -d= -f2; }
swget() { echo "${SW_STATS}" | grep -oE "(^| )$1=[^ ]*" | tr -d ' ' | cut -d= -f2; }
MISM_ALL=$(dcget mism_absmax_all); MISM_ALL_AT=$(echo "${DC_STATS}" | grep '^DCSUM' | sed -n 's/.*mism_absmax_all_at=\([^ ]*\).*/\1/p')
MISM_NOM=$(dcget mism_absmax_nom)
FLAT_NOM=$(dcget flat_max_nom)
SATLO=$(dcget satmarg_lo_min); SATHI=$(dcget satmarg_hi_min); NSATFAIL=$(dcget nsat_fail)
SATMIRLO=$(dcget satmir_lo_min); SATMIRHI=$(dcget satmir_hi_min)
WSKEW=$(swget wskew_absmax); TONSKEW=$(swget ton_skew_absmax)
TONUPMIN=$(swget ton_up_min); TONUPMAX=$(swget ton_up_max)
TONDNMIN=$(swget ton_dn_min); TONDNMAX=$(swget ton_dn_max)
SAT_VERDICT=$([ "${NSATFAIL}" -eq 0 ] && echo "PASS" || echo "FAIL")
TRIM_TABLE=$(echo "${DC_STATS}" | awk '$1 == "TRIM" {printf "  | %d | %.4g | %.4g |\n", $2, $3, $4}')

RECORD="${RECORDSDIR}/${RID}.md"
{
  cat <<EOF
# Record ${RID}

- **Record ID**: ${RID}
- **Claim**: #9 (design-input claim, not a spec line) -- (a) does the charge
  pump hold BOTH current sources in saturation across the whole ~0.9-2.4 V
  Vctrl window of DR-001 Decision 2, at every PVT corner; (b) how large is the
  UP/DN mismatch, in current across that window and in effective switching
  time; and (c) what range and step does the 2-bit Icp trim of DR-001
  Decision 1 actually deliver.  The mismatch numbers are the measured
  SYSTEMATIC part of the up/down mismatch budget stated in
  \`design/README.md\`, which #15's Monte Carlo campaign
  (\`mc-cp-mismatch\`) verifies statistically.
- **Netlist provenance**: schematic (\`design/cp.sch\` and the cells below it)
  exported to SPICE by \`design/netlist.sh\` (xschem batch netlister) ->
  \`sim/cp-compliance/netlist-snapshots/${RID}.spice\`, SHA-256 \`${SHA}\`.
  The testbench decks contain stimulus and measurement only.
- **Environment provenance**:
$(simenv_env_block "$(simenv_xschem_version) (batch netlist export of
    \`design/\` via \`design/netlist.sh\`; the DUT netlist is a schematic
    export, not a hand-written deck)")
- **Corner matrix run**: ${CORNER_DESC}
  - Bundles (-> \`.lib\` sections of sm141064.ngspice): \`typical\` -> typical;
    \`ff\` -> ff; \`ss\` -> ss; \`fs\` -> fs; \`sf\` -> sf
  - Temperature: -40 C, 27 C, 125 C
  - Supply: 2.97 V, 3.30 V, 3.63 V (3.3 V +/-10%)
  - **Axes not swept**: passive corner sections (\`res_*\`, \`mimcap_*\`,
    \`moscap_*\`) N/A -- the DUT is \`nfet_03v3\`/\`pfet_03v3\` only (DR-002
    Decision 3); it contains no resistors or capacitors.
- **Methodology / criteria / limitations**:
  - **Compliance / saturation criterion**: not inferred from the flatness of
    the I-V curve but read off the devices -- at Vctrl = ${VLO} V and
    Vctrl = ${VHI} V the record reports the smallest \`|vds| - |vdsat|\` among
    the two output CASCODE devices.  Positive at both ends, at every corner and
    trim code, is the pass condition.  The cascode is the right device to key
    the verdict on: it is the one whose operating point the output voltage
    actually moves.  The bottom mirror devices are reported separately for
    context -- a wide-swing cascode bias deliberately parks them AT the
    saturation boundary (that is what buys the headroom) and their bias is set
    by the mirror, not by Vctrl, so a margin near zero there is the design
    working as intended rather than a compliance failure.  Current flatness
    across the window is reported alongside as the consequence.
  - **Mismatch measurement topology**: two charge-pump instances, one hardwired
    UP-active and one DN-active, share ONE swept output node through separate
    0 V ammeters, so both polarities are measured at identical output voltages
    in a single DC sweep.  Both instances always carry the same trim code,
    because DR-001's 2-bit trim is a single shared code.
  - **Timing-mismatch measurement**: the DC sweep cannot see switching
    asymmetry, so a second bench pulses each polarity from the SAME control
    edge into a control node held at Vctrl, and reports \`w_eff = q / i_ss\`
    per polarity -- the effective pulse width the loop actually sees, including
    the tail-node charge-sharing transient at switch-on.  \`wskew = w_up -
    w_dn\` is the effective UP/DN timing mismatch in seconds.
  - **Bias generation is out of scope and idealized**: the four bias nodes
    (bottom-mirror and wide-swing-cascode diode, per polarity) are driven from
    ideal current sources, exactly as in \`sim/devchar-cp\` -- at 4x the
    unit-leg current, because the bias diodes are 4x the unit geometry (the
    mirror ratio into each leg is therefore 1x, while the bias nodes get 4x
    the transconductance to drive the legs' aggregate gate capacitance).  The
    mismatch
    reported here is therefore the OUTPUT STAGE's own; a real reference
    generator adds its own contribution, which \`design/README.md\` carries as
    a separate line of the budget.
  - DC sweep: 0 to 3.63 V in 20 mV steps.  ngspice's control-mode \`dc\` does
    not accept a parameter reference for its sweep bounds, so the sweep runs to
    the top of the supply grid at every corner -- a superset of each corner's
    own range; the extraction uses each corner's actual window and ignores the
    surplus points.
  - \`rshunt = 1e12\` is set: a disabled trim leg's cascode mid-node is driven
    only by two off devices and is floating for the DC solution.  It
    contributes 3.3 pA at 3.3 V, below the abstol floor of the measurement.
  - **Limitation (nominal skew only)**: \`sw_stat_global = sw_stat_mismatch =
    0\`.  Everything here is systematic; RANDOM device mismatch is #15's
    campaign, and this record's numbers are what that distribution should be
    centred on.$(method_note)
- **Statistical convention**: N/A -- corner-matrix claim, not a distribution
  claim.
- **Result**:

  **Icp trim range** (mean of the two polarities at Vctrl = ${VMID} V,
  min/max across all ${NCORNERS} corners):

  | Unit legs (1 + b0 + 2*b1) | Icp min (A) | Icp max (A) |
  |---|---|---|
${TRIM_TABLE}

  **Compliance / saturation** across the ${VLO} - ${VHI} V window:
  - Smallest CASCODE saturation margin at Vctrl = ${VLO} V: ${SATLO} V
  - Smallest CASCODE saturation margin at Vctrl = ${VHI} V: ${SATHI} V
  - Bottom mirror devices, same quantity (context, not the verdict -- the
    wide-swing bias parks them at the boundary by construction and their bias
    does not move with the output voltage): ${SATMIRLO} V at Vctrl = ${VLO} V,
    ${SATMIRHI} V at Vctrl = ${VHI} V
  - Corners/codes with a device out of saturation inside the window:
    ${NSATFAIL}
  - Largest peak-to-peak current variation across the window at the nominal
    trim code: ${FLAT_NOM} % (of the mid-window value)
  - **Compliance verdict: ${SAT_VERDICT}**

  **UP/DN mismatch (systematic, nominal skew)**:
  - Current mismatch, worst point inside the window at the nominal trim code:
    ${MISM_NOM} %
  - Current mismatch, worst over ALL corners and ALL trim codes: ${MISM_ALL} %
    at \`${MISM_ALL_AT}\`
  - Effective switching-time skew \`w_up - w_dn\`, worst over all corners and
    all three Vctrl points: ${WSKEW} s
  - 50 % turn-on delay: UP ${TONUPMIN} to ${TONUPMAX} s, DN ${TONDNMIN} to
    ${TONDNMAX} s; worst UP-vs-DN turn-on skew ${TONSKEW} s

  Full tables: \`sim/cp-compliance/corners/${RID}/cp_dc.csv\` (per corner per
  trim code), \`cp_switch.csv\` (per corner per Vctrl), \`cp_curves.csv\`
  (decimated output I-V curves through both knees).
- **Links**:
  - Testbenches: \`sim/cp-compliance/testbench/tb_cp_dc.sp\`,
    \`sim/cp-compliance/testbench/tb_cp_switch.sp\`,
    \`sim/cp-compliance/testbench/run.sh\`
  - Design: \`design/cp.sch\`, \`design/cp_leg_n.sch\`, \`design/cp_leg_p.sch\`,
    \`design/cp_dumpbuf.sch\`
  - Netlist snapshot: \`sim/cp-compliance/netlist-snapshots/${RID}.spice\`
  - Raw logs: \`sim/cp-compliance/corners/${RID}/\`
  - Extracted metrics: \`sim/cp-compliance/corners/${RID}/cp_dc.csv\`,
    \`cp_switch.csv\`, \`cp_curves.csv\`
$(author_field)
$(supersedes_field)
EOF
} >"${RECORD}"

echo "cp-compliance: wrote ${RECORD}"
echo "cp-compliance: wrote ${OUT_DC}, ${OUT_SW}, ${OUT_CURVES}"
echo "cp-compliance: wrote ${CORNERSDIR}/ ($(( NDC + NSW )) corner logs)"
