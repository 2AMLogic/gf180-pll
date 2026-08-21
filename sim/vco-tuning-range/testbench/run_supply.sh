#!/usr/bin/env bash
# gf180-pll :: vco-tuning-range :: supply-pushing + supply-induced-jitter campaign
#
# SUPERSEDED FOR NEW RUNS by this campaign's sim/harness manifest
# (testbench-supply/tb.json + derive_supply.py) -- run
#   python3 sim/run_corners.py sim/vco-tuning-range/testbench-supply
# instead (#124). This script is kept because the records it already minted
# are append-only evidence and it is the only thing that can regenerate the
# extra CSV artifacts they cite; do not extend it.
#
# Two testbenches, one record, because they answer two halves of the same
# question and the second is meaningless without the first:
#
#   tb_vco_pushing.sp        STATIC pushing -- f_osc vs. vdd_vco at 7 supply
#                            points across the ratified 3.3 V +/-10 % rail,
#                            seven independent VCO copies in one transient.
#   tb_vco_supply_jitter.sp  TRANSIENT response -- a supply step and a
#                            supply ripple, against a quiet reference copy that
#                            establishes the transient solver's own numerical
#                            jitter floor. DR-001 names this the top technical
#                            risk of the current-starved single-ended ring and
#                            names its absence as grounds to supersede the
#                            architecture decision.
#
# Phases (each row of the grid is one ngspice run):
#   push  7 bundles x 3 temps x 3 bands (B0/B4/B7) at Vctrl 1.8 V   =  63 runs
#   jit   7 bundles x 3 temps x 3 supplies, band 5, Vctrl 1.8 V     =  63 runs
#   band  3 bundles x band 0..7 at the nominal temp/supply          =  24 runs
#   frip  3 bundles x band 5 at ripple f_osc/4 and f_osc/32         =   6 runs
#
# Usage:
#   ./run_supply.sh              # full campaign -> mints a records/<id>.md
#   ./run_supply.sh --check      # one pushing point + one jitter point, stdout
#   SIM_JOBS=8 ./run_supply.sh   # cap parallelism
#
#   SIM_SUPERSEDES=<record-id> SIM_SUPERSEDES_NOTE='<why>' ./run_supply.sh
#                            mint the record with a **Supersedes** field naming
#                            the record this run replaces (sim/README.md ::
#                            "Status / supersession language").  Set at mint
#                            time on purpose -- editing the field into a
#                            generated record afterwards is a record rewrite.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP="$(cd "${HERE}/.." && pwd)"
REPO="$(cd "${EXP}/../.." && pwd)"
# shellcheck source=../../lib/simenv.sh
. "${HERE}/../../lib/simenv.sh"
# shellcheck source=common.sh
. "${HERE}/common.sh"

PUSH_DECK="${HERE}/tb_vco_pushing.sp"
JIT_DECK="${HERE}/tb_vco_supply_jitter.sp"
DUT="${REPO}/design/netlist/vco.spice"
WORK="${EXP}/work-supply"

BUNDLES=(typical ff ss fs sf all-slow all-fast)
SPOT_BUNDLES=(typical all-slow all-fast)
PUSH_BANDS=(0 4 7)
PUSH_VCTRL=1.8
JIT_BAND=5
JIT_VCTRL=1.8
# Supply perturbations. 100 mV is ~3 % of the 3.3 V rail: a realistic on-chip
# droop, small enough to stay in the linear pushing regime and large enough to
# sit far above the numerical floor the quiet copy measures.
ASTEP=0.1
ARIP=0.05
TEDGE=1n
# Supply-pushing internal sweep points of tb_vco_pushing.sp, in deck order.
PUSH_SUPPLIES=(2.97 3.08 3.19 3.30 3.41 3.52 3.63)

PUSH_HEADER="bundle,temp_c,band,vctrl_v,vdd_v,fosc_hz,isupply_a"
JIT_HEADER="bundle,temp_c,vdd_v,band,vctrl_v,ripple_div,arip_v,astep_v,frip_hz,\
quiet_f_hz,quiet_tj_pp_s,quiet_tj_rms_s,quiet_c2c_rms_s,quiet_tie_pp_s,quiet_tie_rms_s,\
step_f_pre_hz,step_f_post_hz,step_df_hz,step_kvdd_hz_per_v,step_tie_per_us_s,\
rip_f_hz,rip_tj_pp_s,rip_tj_rms_s,rip_c2c_rms_s,rip_tie_pp_s,rip_tie_rms_s,\
rip_tie_pp_pred_s,rip_tj_pp_pred_s,quiet_cycles,rip_cycles"

# --------------------------------------------------------------------------
# One static-pushing point: 7 CSV rows (one per supply) on stdout.
# --------------------------------------------------------------------------
push_one() {
  local bundle="$1" temp="$2" band="$3" vctrl="$4"
  local b0=$((band & 1)) b1=$(((band >> 1) & 1)) b2=$(((band >> 2) & 1))
  local tag
  tag=$(run_tag push "${bundle}" "T${temp}" "B${band}" "V${vctrl}")

  # Window sized by the SLOWEST copy (2.97 V is not always the slowest, so take
  # the min estimate over the swept supplies) and stepped for the fastest.
  local flo fhi f v
  flo=""; fhi=""
  for v in "${PUSH_SUPPLIES[@]}"; do
    f=$(f_est "${band}" "${vctrl}" "${bundle}" "${temp}" "${v}")
    flo=$(python3 -c "print(min(${f}, ${flo:-${f}}))")
    fhi=$(python3 -c "print(max(${f}, ${fhi:-${f}}))")
  done

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
    if simenv_run_deck "${PUSH_DECK}" "${WORK}" "${tag}" "${libs}" "${temp}" \
        "vsup=${PUSH_SUPPLIES[3]}" "vctrl=${vctrl}" "b0=${b0}" "b1=${b1}" "b2=${b2}" \
        "tsettle=${tsettle}" "tstop=${tstop}" "tstep=${tmax}" "tmax=${tmax}" \
        >/dev/null 2>&1
    then
      local ngood
      ngood=$(grep -cE "^ *f[1-7] *=" "${rundir}/ngspice.log" || true)
      [ "${ngood}" -eq 7 ] && { ok=1; break; }
    fi
    attempt=$((attempt + 1))
    stretch=$((stretch * 3))
  done
  [ "${ok}" -eq 1 ] || { echo "ERROR: ${tag} did not converge" >&2; return 1; }

  local log="${rundir}/ngspice.log" i
  for i in 1 2 3 4 5 6 7; do
    local fm cur
    fm=$(simenv_meas "${log}" "f${i}")
    cur=$(simenv_meas "${log}" "i${i}")
    awk -v b="${bundle}" -v t="${temp}" -v bd="${band}" -v vc="${vctrl}" \
        -v v="${PUSH_SUPPLIES[$((i - 1))]}" -v f="${fm}" -v c="${cur}" \
        'function abs(x){return x<0?-x:x} BEGIN{printf "%s,%s,%s,%s,%s,%.7g,%.6g\n", b,t,bd,vc,v,f,abs(c)}'
  done
}

# --------------------------------------------------------------------------
# One transient supply point: 1 CSV row on stdout.
# --------------------------------------------------------------------------
jit_one() {
  local bundle="$1" temp="$2" vdd="$3" band="$4" vctrl="$5" ripdiv="$6"
  local b0=$((band & 1)) b1=$(((band >> 1) & 1)) b2=$(((band >> 2) & 1))
  local tag
  tag=$(run_tag jit "${bundle}" "T${temp}" "V${vdd}" "B${band}" "C${vctrl}" "R${ripdiv}")

  local f
  f=$(f_est "${band}" "${vctrl}" "${bundle}" "${temp}" "${vdd}")

  local rundir="${WORK}/${tag}"
  mkdir -p "${rundir}"
  cp "${WORK}/vco.spice" "${rundir}/vco.spice"

  # ncyc is always 4 whole ripple periods (>= 64 cycles), so the peak-to-peak
  # TIE the record reports is a real peak-to-peak and not a fragment of one
  # modulation cycle. The step lands at the window midpoint.
  local vals
  vals=$(python3 -c "
f=${f}; rd=${ripdiv}
ncyc=max(64.0, 4.0*rd)
ts=6.0/f
win=ncyc/f
print('%.6g %.6g %.6g %.6g %.6g' % (ts, ts+win, ts+win/2.0, 1.0/(200*f), f/rd))")
  read -r tsettle tstop tstepon tmax frip <<<"${vals}"

  local libs attempt=0 ok=0
  libs=$(bundle_libs "${bundle}")
  while [ "${attempt}" -lt 2 ]; do
    if simenv_run_deck "${JIT_DECK}" "${WORK}" "${tag}" "${libs}" "${temp}" \
        "vsup=${vdd}" "vctrl=${vctrl}" "b0=${b0}" "b1=${b1}" "b2=${b2}" \
        "astep=${ASTEP}" "tstepon=${tstepon}" "tedge=${TEDGE}" \
        "arip=${ARIP}" "frip=${frip}" \
        "tsettle=${tsettle}" "tstop=${tstop}" "tstep=${tmax}" "tmax=${tmax}" \
        >/dev/null 2>&1 && [ -s "${rundir}/jit.dat" ]
    then
      ok=1; break
    fi
    attempt=$((attempt + 1))
  done
  [ "${ok}" -eq 1 ] || { echo "ERROR: ${tag} ngspice failed" >&2; return 1; }

  local row
  row=$(python3 "${HERE}/jitter_extract.py" "${rundir}/jit.dat" "${vdd}" \
      "${tsettle}" "${tstepon}" "${ASTEP}" "${ARIP}" "${frip}" \
      "${rundir}/periods.csv") || return 1
  printf '%s,%s,%s,%s,%s,%s,%s,%s,%.6g,%s\n' \
    "${bundle}" "${temp}" "${vdd}" "${band}" "${vctrl}" "${ripdiv}" \
    "${ARIP}" "${ASTEP}" "${frip}" "${row}"
}

# --------------------------------------------------------------------------
# Entry points
# --------------------------------------------------------------------------
case "${1:-}" in
  --push-one) shift; push_one "$@"; exit 0 ;;
  --jit-one)  shift; jit_one  "$@"; exit 0 ;;
esac

simenv_require_tools
[ -f "${DUT}" ] || { echo "ERROR: ${DUT} missing -- run design/netlist.sh" >&2; exit 1; }
mkdir -p "${WORK}"
cp "${DUT}" "${WORK}/vco.spice"

if [ "${1:-}" = "--check" ]; then
  echo "${PUSH_HEADER}"
  push_one typical 27 5 "${PUSH_VCTRL}"
  echo "${JIT_HEADER}"
  jit_one typical 27 3.30 5 "${JIT_VCTRL}" 16
  exit 0
fi

# ---- job lists -------------------------------------------------------------
PJOBS="${WORK}/push_jobs.txt"; : >"${PJOBS}"
for bundle in "${BUNDLES[@]}"; do
  for temp in "${SIMENV_TEMPS[@]}"; do
    for band in "${PUSH_BANDS[@]}"; do
      echo "${bundle} ${temp} ${band} ${PUSH_VCTRL}" >>"${PJOBS}"
    done
  done
done

JJOBS="${WORK}/jit_jobs.txt"; : >"${JJOBS}"
for bundle in "${BUNDLES[@]}"; do
  for temp in "${SIMENV_TEMPS[@]}"; do
    for vdd in "${SIMENV_VDDS[@]}"; do
      echo "${bundle} ${temp} ${vdd} ${JIT_BAND} ${JIT_VCTRL} 16" >>"${JJOBS}"
    done
  done
done
for bundle in "${SPOT_BUNDLES[@]}"; do
  for band in 0 1 2 3 4 5 6 7; do
    echo "${bundle} 27 3.30 ${band} ${JIT_VCTRL} 16" >>"${JJOBS}"
  done
  for rd in 4 32; do
    echo "${bundle} 27 3.30 ${JIT_BAND} ${JIT_VCTRL} ${rd}" >>"${JJOBS}"
  done
done

# The band sweep's band-5 entries coincide exactly with three points of the main
# PVT grid. Simulating the same parameter set twice would be wasted runtime and
# would double-count those corners in the record, so the transient job list is
# deduplicated before anything runs.
sort -u "${JJOBS}" -o "${JJOBS}"

NP=$(wc -l <"${PJOBS}" | tr -d ' ')
NJ=$(wc -l <"${JJOBS}" | tr -d ' ')
echo "vco supply campaign: ${NP} pushing runs (x7 supply points) + ${NJ} transient runs, $(simenv_jobs) parallel jobs"

PROWS="${WORK}/push_rows.csv"
JROWS="${WORK}/jit_rows.csv"

# Resumable for the same reason `run.sh` is: the runs are deterministic, so a
# point re-run in a later pass produces byte-identical output. `--resume` keeps
# the rows already collected and re-runs only the missing points; with nothing
# missing it goes straight to minting the record, which is also how a corrected
# extraction is re-applied to an unchanged simulation set.
if [ "${1:-}" = "--resume" ] && [ -s "${PROWS}" ]; then
  sort -u "${PROWS}" -o "${PROWS}"
  awk -F, '{c[$1","$2","$3","$4]++} END {for (k in c) if (c[k] == 7) print k}' \
    "${PROWS}" >"${WORK}/push_done.txt"
  awk -F, 'NR==FNR{d[$0];next}{if (($1","$2","$3","$4) in d) print}' \
    "${WORK}/push_done.txt" "${PROWS}" >"${PROWS}.keep" && mv "${PROWS}.keep" "${PROWS}"
  awk 'NR==FNR{d[$0];next}{k=$1","$2","$3","$4; if (!(k in d)) print}' \
    "${WORK}/push_done.txt" "${PJOBS}" >"${WORK}/push_pending.txt"
  sort -u "${JROWS}" -o "${JROWS}" 2>/dev/null || : >"${JROWS}"
  awk -F, '{print $1" "$2" "$3" "$4" "$5" "$6}' "${JROWS}" >"${WORK}/jit_done.txt"
  awk 'NR==FNR{d[$0];next}{if (!($0 in d)) print}' \
    "${WORK}/jit_done.txt" "${JJOBS}" >"${WORK}/jit_pending.txt"
else
  : >"${PROWS}"; : >"${JROWS}"
  cp "${PJOBS}" "${WORK}/push_pending.txt"
  cp "${JJOBS}" "${WORK}/jit_pending.txt"
fi
echo "vco supply campaign: $(wc -l <"${WORK}/push_pending.txt" | tr -d ' ') pushing + $(wc -l <"${WORK}/jit_pending.txt" | tr -d ' ') transient runs still to do"

if [ -s "${WORK}/push_pending.txt" ]; then
  # shellcheck disable=SC2016
  xargs -P "$(simenv_jobs)" -L 1 \
    "${BASH:-/bin/bash}" -c 'exec "$0" --push-one "$@"' "${HERE}/run_supply.sh" \
    <"${WORK}/push_pending.txt" >>"${PROWS}"
fi
sort -u "${PROWS}" -o "${PROWS}"
GOT=$(wc -l <"${PROWS}" | tr -d ' ')
[ "${GOT}" -eq $((NP * 7)) ] || {
  echo "ERROR: expected $((NP * 7)) pushing rows, collected ${GOT} -- re-run with --resume" >&2
  exit 1; }

if [ -s "${WORK}/jit_pending.txt" ]; then
  # shellcheck disable=SC2016
  xargs -P "$(simenv_jobs)" -L 1 \
    "${BASH:-/bin/bash}" -c 'exec "$0" --jit-one "$@"' "${HERE}/run_supply.sh" \
    <"${WORK}/jit_pending.txt" >>"${JROWS}"
fi
sort -u "${JROWS}" -o "${JROWS}"
GOT=$(wc -l <"${JROWS}" | tr -d ' ')
[ "${GOT}" -eq "${NJ}" ] || {
  echo "ERROR: expected ${NJ} jitter rows, collected ${GOT} -- re-run with --resume" >&2
  exit 1; }

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

# One committed log per PVT point: the pushing run for that point followed by
# every transient run at it, so a corner-id log is self-contained.
while read -r bundle temp band vctrl; do
  cid=$(simenv_corner_id "${bundle}" "${temp}" "${PUSH_SUPPLIES[3]}")
  tag=$(run_tag push "${bundle}" "T${temp}" "B${band}" "V${vctrl}")
  {
    echo "======== pushing sweep, band ${band}, Vctrl ${vctrl} V (${cid}) ========"
    cat "${WORK}/${tag}/deck.sp"
    echo
    echo "======== ngspice output ========"
    cat "${WORK}/${tag}/ngspice.log"
    echo
  } >>"${CORNERSDIR}/${cid}.log"
done <"${PJOBS}"

while read -r bundle temp vdd band vctrl rd; do
  cid=$(simenv_corner_id "${bundle}" "${temp}" "${vdd}")
  tag=$(run_tag jit "${bundle}" "T${temp}" "V${vdd}" "B${band}" "C${vctrl}" "R${rd}")
  {
    echo "======== supply transient, band ${band}, Vctrl ${vctrl} V, ripple f/${rd} (${cid}) ========"
    cat "${WORK}/${tag}/deck.sp"
    echo
    echo "======== ngspice output ========"
    cat "${WORK}/${tag}/ngspice.log"
    echo
  } >>"${CORNERSDIR}/${cid}.log"
done <"${JJOBS}"

PUSH_CSV="${CORNERSDIR}/supply_pushing.csv"
{
  simenv_provenance "vco-tuning-range (supply pushing)" "${RID}" \
    "design/vco.sch -> sim/vco-tuning-range/netlist-snapshots/${RID}.spice" \
    "7 bundles x temp{-40,27,125}C x band{0,4,7} x vdd{2.97..3.63 in 0.11 V} at Vctrl ${PUSH_VCTRL} V"
  cat <<'EOF'
# deck: tb_vco_pushing.sp -- seven independent VCO copies, one per supply
#   point, each with its own supply source, ammeter and rail-referenced band
#   code. fosc measured at that copy's buffered CLK against its own half-supply
#   threshold, over 4 whole cycles after tsettle.
EOF
  echo "${PUSH_HEADER}"
  sort -t, -k1,1 -k2,2n -k3,3n -k5,5n "${PROWS}"
} >"${PUSH_CSV}"

JIT_CSV="${CORNERSDIR}/supply_jitter.csv"
{
  simenv_provenance "vco-tuning-range (supply jitter)" "${RID}" \
    "design/vco.sch -> sim/vco-tuning-range/netlist-snapshots/${RID}.spice" \
    "7 bundles x temp{-40,27,125}C x vdd{2.97,3.30,3.63}V at band ${JIT_BAND}, plus a band sweep and a ripple-frequency sweep at 3 bundles"
  cat <<EOF
# deck: tb_vco_supply_jitter.sp -- three VCO copies per run, quiet / stepped /
#   rippled supply, all other conditions identical. The quiet copy is the
#   numerical jitter floor of the transient solver at these settings, not a
#   circuit result; every supply-induced number is reported against it.
# step: ${ASTEP} V step with a ${TEDGE} edge at the window midpoint
# ripple: ${ARIP} V amplitude sine at f_osc/<ripple_div>, 4 whole ripple periods
#   inside the measurement window
# *_pred: quasi-static prediction from the measured transient pushing
#   coefficient -- TIE_pp = K*A/(pi*f_rip*f_osc), period_pp = 2*T0*K*A/f_osc.
#   Agreement is what licenses projecting these numbers to ripple frequencies
#   other than the ones simulated.
EOF
  echo "${JIT_HEADER}"
  sort -t, -k1,1 -k2,2n -k3,3n -k4,4n -k6,6n "${JROWS}"
} >"${JIT_CSV}"

# Commit the per-cycle period/TIE sequence for the nominal point and for the
# worst-jitter point (sim/README.md's waveform rule: commit the extracted
# signal, never the rawfile).
WORSTTAG=$(python3 - "${JIT_CSV}" <<'PY'
import csv, sys
rows = [r for r in open(sys.argv[1]) if not r.startswith('#')]
best = max(csv.DictReader(rows), key=lambda r: float(r['rip_tie_pp_s']))
print("jit_%s_T%s_V%s_B%s_C%s_R%s" % (best['bundle'], best['temp_c'], best['vdd_v'],
                                      best['band'], best['vctrl_v'], best['ripple_div']))
PY
)
WORSTTAG="${WORSTTAG//./p}"; WORSTTAG="${WORSTTAG//-/m}"
NOMTAG=$(run_tag jit typical T27 V3.30 "B${JIT_BAND}" "C${JIT_VCTRL}" R16)
for t in "${NOMTAG}" "${WORSTTAG}"; do
  [ -f "${WORK}/${t}/periods.csv" ] && cp "${WORK}/${t}/periods.csv" \
    "${CORNERSDIR}/periods_${t}.csv"
done

RESULT="${WORK}/result.md"
python3 "${HERE}/analyze_supply.py" "${PUSH_CSV}" "${JIT_CSV}" >"${RESULT}"

RECORD="${RECORDSDIR}/${RID}.md"
{
  cat <<EOF
# Record ${RID}

- **Record ID**: ${RID}
- **Claim**: #8 (design-input claim feeding two spec lines) -- how much does
  \`vdd_vco\` move the ring VCO's frequency, statically and in a transient, and
  what timing error does a realistic supply disturbance therefore inject?
  DR-001's Consequences section names this the accepted risk of the
  current-starved single-ended ring and states the requirement in terms this
  record answers: "#8 must produce a supply-step/supply-noise jitter testbench,
  not just a clean-supply Kvco sweep. This is the number most likely to force a
  supersede." Feeds #14's supply-sensitivity budget and #13's jitter budget.
  Spec-line references are placeholders pending ratification (#1):
  \`spec/pll.md#supply-sensitivity\`, \`spec/pll.md#period-jitter\`.
- **Netlist provenance**: schematic (\`design/vco.sch\` + \`design/vco_bias.sch\`
  + \`design/vco_stage.sch\`, exported by \`design/netlist.sh\`) ->
  \`sim/vco-tuning-range/netlist-snapshots/${RID}.spice\`, SHA-256 \`${SHA}\`
- **Environment provenance**:
$(simenv_env_block)
- **Corner matrix run**: two grids, one per testbench.
  - **Static pushing** (\`tb_vco_pushing.sp\`): 7 bundles x 3 temperatures x 3
    band codes (B0/B4/B7) at Vctrl ${PUSH_VCTRL} V = ${NP} runs, each sweeping
    **7 supply points** internally (2.97, 3.08, 3.19, 3.30, 3.41, 3.52,
    3.63 V) = $((NP * 7)) measured points. The supply axis is finer than
    \`sim/README.md\`'s 3-point default because the quantity being measured IS
    the supply derivative; 3 points cannot show its curvature.
  - **Transient response** (\`tb_vco_supply_jitter.sp\`): the full default PVT
    grid -- 7 bundles x 3 temperatures x 3 supplies = 63 points -- at band
    ${JIT_BAND}, Vctrl ${JIT_VCTRL} V, ripple at f_osc/16. Plus a band sweep
    (bands 0-7 at 3 bundles, nominal temp/supply) and a ripple-frequency check
    (f_osc/4 and f_osc/32 at 3 bundles) = ${NJ} runs total.
  - Bundles (-> \`.lib\` sections of \`sm141064.ngspice\`):
    \`typical\`/\`ff\`/\`ss\`/\`fs\`/\`sf\` -> that MOS section + res_typical +
    moscap_typical; \`all-slow\` -> ss + res_ss + moscap_ss; \`all-fast\` -> ff +
    res_ff + moscap_ff.
  - **Axes deliberately reduced, with reasons**: the transient grid runs one
    band and one control voltage at every PVT point rather than all 56
    (band, Vctrl) combinations. Band ${JIT_BAND} at Vctrl ${JIT_VCTRL} V is
    ~100 MHz, the frequency the draft jitter line is quoted at, and the band
    sweep above shows the band dependence separately at three bundles. The
    static-pushing grid runs three bands rather than eight for the same reason:
    B0/B4/B7 bracket the geometric band map. MIM sections are N/A (no MIM
    device in this DUT).
- **Methodology / criteria / limitations**:
  - **Static pushing measurement criterion**: seven independent VCO copies, one
    per supply point, in a single transient. Each copy carries its own supply
    source, its own ammeter and its own band-code sources **referenced to that
    copy's rail** -- a shared logic-level band code would leave the
    band-select pass gates of the higher-rail copies partly on and corrupt the
    measurement. Frequency is taken at each copy's buffered \`CLK\` over four
    whole cycles after a settle window of >= 4 estimated periods.
  - **Transient measurement criterion**: three VCO copies per run, identical
    except for their supply drive -- quiet (dc), stepped (${ASTEP} V step,
    ${TEDGE} edge, at the window midpoint) and rippled (${ARIP} V amplitude
    sine). Every reported number comes from **interpolated half-supply
    crossings of the buffered output**, extracted by \`jitter_extract.py\`, not
    from \`.meas\`: jitter is a property of the period *sequence* and \`.meas\`
    reports scalars. The window always holds four whole ripple periods, so a
    peak-to-peak TIE is a real peak-to-peak.
  - **The quiet copy is the noise floor, not a result.** Any period variation
    it shows is the transient solver's own local truncation error at these
    settings (\`reltol = 1e-4\`, max timestep 1/(200 f_osc)). The record reports
    the stepped and rippled numbers **against** that floor; where a number is
    not comfortably above it, the record says so instead of quoting it.
  - **Quasi-static model, and why it is checked**: a ring VCO's supply
    response is flat well beyond any supply-noise frequency of interest, so
    f(t) = f0 + K_vdd*v_ripple(t) predicts TIE_pp = K*A/(pi*f_rip*f0) and
    period modulation 2*T0*K*A/f0. Both predictions are computed from the
    *measured transient* K_vdd and compared with the measured jitter at three
    ripple frequencies (f_osc/4, /16, /32). Agreement is what licenses
    projecting these numbers to ripple frequencies that were not simulated;
    disagreement would mean they cannot be projected, and the record would say
    that instead.
  - **Limitations**:
    - **Open loop.** No PLL is closed around this VCO here, so nothing corrects
      the supply-induced frequency error. The reported TIE is therefore an
      upper bound for supply disturbances *inside* the (not yet designed) loop
      bandwidth and approximately correct for disturbances above it. The
      closed-loop number is #12/#13's, and it cannot be produced before #9/#10
      fix the loop bandwidth.
    - **Deterministic disturbances only.** This record injects a step and a
      sinusoid. It is not a random-noise (phase-noise) simulation and reports
      no random jitter number; \`sim/README.md\`'s worked example and #13 both
      flag ngspice transient noise as a separate, harder question.
    - **Schematic level.** No supply-network parasitics: the rail is driven by
      an ideal source through the on-chip decap only. Real bond-wire and
      on-die rail impedance will make the *disturbance* larger for a given
      external event; this record characterizes the VCO's sensitivity to a rail
      disturbance, not the disturbance itself.
    - Statistical switches: \`sw_stat_global = sw_stat_mismatch = 0\`.
- **Statistical convention**: N/A -- corner-matrix claim, not a distribution
  claim. The reported RMS values are RMS *over the measured cycle sequence* of
  a deterministic disturbance, not a stochastic estimate.
- **Result**:

EOF
  cat "${RESULT}"
  cat <<EOF

- **Links**:
  - Testbenches: \`sim/vco-tuning-range/testbench/tb_vco_pushing.sp\`,
    \`sim/vco-tuning-range/testbench/tb_vco_supply_jitter.sp\`
  - Corner runner: \`sim/vco-tuning-range/testbench/run_supply.sh\`
  - Extraction: \`sim/vco-tuning-range/testbench/jitter_extract.py\`,
    \`sim/vco-tuning-range/testbench/analyze_supply.py\`
  - Netlist snapshot: \`sim/vco-tuning-range/netlist-snapshots/${RID}.spice\`
  - Raw logs: \`sim/vco-tuning-range/corners/${RID}/\` (one per PVT point)
  - Extracted metrics: \`corners/${RID}/supply_pushing.csv\`,
    \`corners/${RID}/supply_jitter.csv\`
  - Per-cycle period/TIE sequences (the waveform evidence behind the jitter
    numbers, extracted rather than committed as a rawfile per
    \`sim/README.md\`): \`corners/${RID}/periods_*.csv\`
- **Timestamp / author**: $(date -u +%Y-%m-%dT%H:%M:%SZ), agent-builder (#8)
$(simenv_supersedes_field "${SIM_SUPERSEDES:-}")
EOF
} >"${RECORD}"

echo "vco supply campaign: wrote ${PUSH_CSV}"
echo "vco supply campaign: wrote ${JIT_CSV}"
echo "vco supply campaign: wrote ${RECORD}"
echo "${RID}" >"${WORK}/last_record_id"
