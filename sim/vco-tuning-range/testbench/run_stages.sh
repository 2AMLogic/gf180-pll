#!/usr/bin/env bash
# gf180-pll :: vco-tuning-range :: odd-stage-count confirmation campaign
#
# DR-001 Decision 2 fixes the delay cell and leaves the stage count open:
# "odd stage count (5 nominal; #8 to confirm against the 200 MHz top of band and
# the power budget)". `tb_vco_stages.sp` runs 3-, 5- and 7-stage rings built
# from the same cell and the same bias generator side by side in one deck; this
# runner sweeps that deck and mints the record that closes the question.
#
# Grid: 3 PVT points x 8 band codes x 2 control voltages = 48 runs.
#   Corners: the nominal point plus the extreme-slow and extreme-fast composite
#   corners the 63-point tuning campaign identified. This is a REDUCED grid and
#   the record says so with its reason: the three rings sit in the same deck at
#   the same corner, so this is a *relative* comparison whose ranking is monotone
#   in N; the absolute per-corner numbers for the chosen count come from the
#   full-grid tuning record, not from here.
#   Control voltages: the two band edges (0.9 V and 2.7 V). The interior of a
#   band adds nothing to a stage-count decision.
#
# Usage:
#   ./run_stages.sh              # full grid -> mints a records/<id>.md
#   ./run_stages.sh --check      # nominal corner, band 7 top of range, stdout
#   SIM_JOBS=8 ./run_stages.sh   # cap parallelism

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP="$(cd "${HERE}/.." && pwd)"
REPO="$(cd "${EXP}/../.." && pwd)"
# shellcheck source=../../lib/simenv.sh
. "${HERE}/../../lib/simenv.sh"
# shellcheck source=common.sh
. "${HERE}/common.sh"

DECK="${HERE}/tb_vco_stages.sp"
DUT="${REPO}/design/netlist/vco.spice"
WORK="${EXP}/work-stages"

# bundle temp vdd
CORNERS=("typical 27 3.30" "all-slow -40 3.63" "all-fast 125 2.97")
BANDS=(0 1 2 3 4 5 6 7)
VCTRLS=(0.9 2.7)

CSV_HEADER="bundle,temp_c,vdd_v,band,vctrl_v,nstage,fosc_hz,isupply_a,swing_hi_v,swing_lo_v"

run_one() {
  local bundle="$1" temp="$2" vdd="$3" band="$4" vctrl="$5"
  local b0=$((band & 1)) b1=$(((band >> 1) & 1)) b2=$(((band >> 2) & 1))
  local tag
  tag=$(run_tag st "${bundle}" "T${temp}" "V${vdd}" "B${band}" "C${vctrl}")

  # The 7-stage ring is the slowest in the deck (~5/7 of the 5-stage estimate)
  # and the 3-stage the fastest (~5/3), so the window is sized from both ends.
  local f5 flo fhi
  f5=$(f_est "${band}" "${vctrl}" "${bundle}" "${temp}" "${vdd}")
  flo=$(python3 -c "print(${f5}*5.0/7.0)")
  fhi=$(python3 -c "print(${f5}*5.0/3.0)")

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
        "vsup=${vdd}" "vctrl=${vctrl}" "b0=${b0}" "b1=${b1}" "b2=${b2}" \
        "tsettle=${tsettle}" "tstop=${tstop}" "tstep=${tmax}" "tmax=${tmax}" \
        >/dev/null 2>&1
    then
      local ngood
      ngood=$(grep -cE "^ *f[357] *=" "${rundir}/ngspice.log" || true)
      [ "${ngood}" -eq 3 ] && { ok=1; break; }
    fi
    attempt=$((attempt + 1))
    stretch=$((stretch * 3))
  done
  [ "${ok}" -eq 1 ] || { echo "ERROR: ${tag} did not converge" >&2; return 1; }

  local log="${rundir}/ngspice.log" n
  for n in 3 5 7; do
    local fm cur hi lo
    fm=$(simenv_meas "${log}" "f${n}")
    cur=$(simenv_meas "${log}" "i${n}")
    hi=$(simenv_meas "${log}" "s${n}hi")
    lo=$(simenv_meas "${log}" "s${n}lo")
    awk -v b="${bundle}" -v t="${temp}" -v v="${vdd}" -v bd="${band}" -v vc="${vctrl}" \
        -v n="${n}" -v f="${fm}" -v c="${cur}" -v hi="${hi}" -v lo="${lo}" \
        'function abs(x){return x<0?-x:x} BEGIN{printf "%s,%s,%s,%s,%s,%s,%.7g,%.6g,%.4g,%.4g\n", b,t,v,bd,vc,n,f,abs(c),hi,lo}'
  done
}

if [ "${1:-}" = "--one" ]; then shift; run_one "$@"; exit 0; fi

simenv_require_tools
[ -f "${DUT}" ] || { echo "ERROR: ${DUT} missing -- run design/netlist.sh" >&2; exit 1; }
mkdir -p "${WORK}"
cp "${DUT}" "${WORK}/vco.spice"

if [ "${1:-}" = "--check" ]; then
  echo "${CSV_HEADER}"
  run_one typical 27 3.30 7 2.7
  exit 0
fi

JOBLIST="${WORK}/jobs.txt"; : >"${JOBLIST}"
for c in "${CORNERS[@]}"; do
  for band in "${BANDS[@]}"; do
    for vctrl in "${VCTRLS[@]}"; do
      echo "${c} ${band} ${vctrl}" >>"${JOBLIST}"
    done
  done
done
NP=$(wc -l <"${JOBLIST}" | tr -d ' ')
echo "vco stage-count campaign: ${NP} runs x 3 stage counts, $(simenv_jobs) parallel jobs"

ROWS="${WORK}/rows.csv"; : >"${ROWS}"
# shellcheck disable=SC2016
xargs -P "$(simenv_jobs)" -L 1 \
  "${BASH:-/bin/bash}" -c 'exec "$0" --one "$@"' "${HERE}/run_stages.sh" \
  <"${JOBLIST}" >>"${ROWS}"
GOT=$(wc -l <"${ROWS}" | tr -d ' ')
[ "${GOT}" -eq $((NP * 3)) ] || {
  echo "ERROR: expected $((NP * 3)) rows, collected ${GOT}" >&2; exit 1; }

RID=$(simenv_record_id)
SNAPDIR="${EXP}/netlist-snapshots"
CORNERSDIR="${EXP}/corners/${RID}"
RECORDSDIR="${EXP}/records"
mkdir -p "${SNAPDIR}" "${CORNERSDIR}" "${RECORDSDIR}"
cp "${DUT}" "${SNAPDIR}/${RID}.spice"
SHA=$(simenv_sha256 "${SNAPDIR}/${RID}.spice")

while read -r bundle temp vdd band vctrl; do
  cid=$(simenv_corner_id "${bundle}" "${temp}" "${vdd}")
  tag=$(run_tag st "${bundle}" "T${temp}" "V${vdd}" "B${band}" "C${vctrl}")
  {
    echo "======== band ${band}, Vctrl ${vctrl} V (${cid}) ========"
    cat "${WORK}/${tag}/deck.sp"
    echo
    echo "======== ngspice output ========"
    cat "${WORK}/${tag}/ngspice.log"
    echo
  } >>"${CORNERSDIR}/${cid}.log"
done <"${JOBLIST}"

CSV_OUT="${CORNERSDIR}/stage_count.csv"
{
  simenv_provenance "vco-tuning-range (stage count)" "${RID}" \
    "design/vco.sch -> sim/vco-tuning-range/netlist-snapshots/${RID}.spice" \
    "3 PVT points x band{0..7} x vctrl{0.9,2.7}V x stage-count{3,5,7} = $((NP * 3)) points"
  cat <<'EOF'
# deck: tb_vco_stages.sp -- 3-, 5- and 7-stage rings in one deck, same
#   vco_stage cell, same vco_bias instance topology, same band code, same
#   control voltage, same corner. Each ring has its own supply ammeter.
# fosc_hz: measured on a ring node over 4 whole cycles after tsettle (no output
#   buffer: the buffer is common to all three counts and only adds a constant).
# swing_hi_v/swing_lo_v: max/min of that ring node in the measurement window --
#   a starved ring that has lost swing is not a usable oscillator, and the
#   3-stage ring is the one at risk of it at the bottom of the band.
EOF
  echo "${CSV_HEADER}"
  sort -t, -k1,1 -k4,4n -k5,5n -k6,6n "${ROWS}"
} >"${CSV_OUT}"

RESULT="${WORK}/result.md"
python3 "${HERE}/analyze_stages.py" "${CSV_OUT}" >"${RESULT}"

RECORD="${RECORDSDIR}/${RID}.md"
{
  cat <<EOF
# Record ${RID}

- **Record ID**: ${RID}
- **Claim**: #8 (design-input claim, not a spec line) -- DR-001 Decision 2
  leaves the ring's stage count open ("odd stage count (5 nominal; #8 to confirm
  against the 200 MHz top of band and the power budget)"). Is 5 the right odd
  count, against 3 and 7, for the ratified 10-200 MHz v1 band (DR-002
  Decision 2)?
- **Netlist provenance**: schematic (\`design/vco_stage.sch\` +
  \`design/vco_bias.sch\`, exported by \`design/netlist.sh\`; the deck
  instantiates those two subcircuits directly rather than the 5-stage
  \`vco\` top level, so all three counts use identical cells) ->
  \`sim/vco-tuning-range/netlist-snapshots/${RID}.spice\`, SHA-256 \`${SHA}\`
- **Environment provenance**:
$(simenv_env_block)
- **Corner matrix run**: $((NP * 3)) points = 3 PVT points x 8 band codes x 2
  control voltages x 3 stage counts.
  - PVT points: \`typical\`/27 C/3.30 V (nominal); \`all-slow\`/-40 C/3.63 V
    (the slowest point on the tuning campaign's 63-point grid);
    \`all-fast\`/125 C/2.97 V (the fastest).
  - Bundles (-> \`.lib\` sections): \`typical\` -> typical, res_typical,
    moscap_typical; \`all-slow\` -> ss, res_ss, moscap_ss; \`all-fast\` -> ff,
    res_ff, moscap_ff.
  - Control voltage: 0.9 V and 2.7 V, the two edges of the usable Vctrl window.
  - **This is a REDUCED grid and the justification is structural, not
    convenience**: all three stage counts are simulated *in the same deck at the
    same corner*, so this record makes a **relative** comparison whose ordering
    is monotone in N. Three PVT points that bracket the whole 63-point grid are
    enough to show the ordering does not invert. The absolute per-corner
    numbers for the count actually chosen come from the full-grid tuning
    record, not from here. Sweeping 63 corners to re-derive a monotone ordering
    would be cost without information -- which is a different argument from
    "the sim was slow", the justification \`sim/README.md\` explicitly refuses.
  - **Axes not swept**: MIM sections N/A (no MIM device in the DUT).
- **Methodology / criteria / limitations**:
  - Measurement criterion: frequency on a ring node (not through the output
    buffer) over four whole cycles after a settle window of >= 4 estimated
    periods; supply current averaged over the same window from each ring's own
    ammeter; peak and trough of the measured ring node over the window, because
    a starved ring that has lost full swing is not a usable oscillator and that
    failure mode is invisible in a frequency number alone.
  - Each ring gets its **own** \`vco_bias\` instance, so a 7-stage ring is not
    loading a bias generator sized for 5 stages -- the comparison is between
    three complete VCOs that differ only in N.
  - Simulator settings: \`.tran\` window scaled per (band, corner, count) from a
    frequency estimate, max timestep <= 1/(80 f_max) for the fastest ring in the
    deck; \`uic\` not used, \`.ic\` on the ring nodes only.
  - Every run is self-checking: all three frequencies must land or the point is
    retried with a 3x longer window; the campaign aborts unless all
    $((NP * 3)) rows are collected.
  - **Limitation**: schematic-level, no parasitics. Stage count changes the
    ratio of self-load to routing load, so extraction (#18) will not scale all
    three counts equally. The margin ordering, not the absolute frequencies, is
    what this record claims.
  - Statistical switches: \`sw_stat_global = sw_stat_mismatch = 0\`.
- **Statistical convention**: N/A -- corner-matrix claim, not a distribution
  claim.
- **Result**:

EOF
  cat "${RESULT}"
  cat <<EOF

- **Links**:
  - Testbench: \`sim/vco-tuning-range/testbench/tb_vco_stages.sp\`
  - Corner runner: \`sim/vco-tuning-range/testbench/run_stages.sh\`
  - Extraction: \`sim/vco-tuning-range/testbench/analyze_stages.py\`
  - Netlist snapshot: \`sim/vco-tuning-range/netlist-snapshots/${RID}.spice\`
  - Raw logs: \`sim/vco-tuning-range/corners/${RID}/\`
  - Extracted metrics: \`sim/vco-tuning-range/corners/${RID}/stage_count.csv\`
- **Timestamp / author**: $(date -u +%Y-%m-%dT%H:%M:%SZ), agent-builder (#8)
- **Supersedes**: (none -- first record for this claim)
EOF
} >"${RECORD}"

echo "vco stage-count campaign: wrote ${CSV_OUT}"
echo "vco stage-count campaign: wrote ${RECORD}"
echo "${RID}" >"${WORK}/last_record_id"
