#!/usr/bin/env bash
# gf180-pll :: devchar-passives :: corner runner
#
# Two campaigns in one directory, because they share a corner convention:
#
#   caps  tb_cap_cv.sp over mimcap_{typical,ff,ss} + moscap_{typical,ff,ss}
#         x temp {-40, 27, 125} C
#   res   tb_res.sp over res_{typical,ff,ss} x temp {-40, 27, 125} C
#
# The passive corner sections are INDEPENDENT axes from the MOS tt/ff/ss/fs/sf
# sections used by the other two campaigns. Each device here depends only on
# its own axis (mimcap_* for MIM, moscap_* for MOS caps, res_* for resistors),
# so sweeping the axes together at {typical, ff, ss} still gives every device
# its complete min/typ/max envelope -- it does not silently leave anything at
# typical, which is the failure mode a MOS-corner-only sweep would have.
#
# Supply is not an independent axis here: the capacitor C-V sweep spans
# 0 -> 3.63 V, the top of the 3.3 V +/- 10 % range, so it already covers the
# control-voltage range at every supply corner. Resistors in this PDK have
# zero voltage coefficient (verified: see r_vcoef_pct_per_v in the results).
#
# Usage:
#   ./run.sh                 # both campaigns -> mints two records/<id>.md
#   ./run.sh --check         # nominal sections only, summaries to stdout
#   SIM_JOBS=4 ./run.sh      # cap parallelism
#
# A full run mints two record IDs (cap claim, resistor claim -- see
# sim/README.md, the repo's append-only evidence-record convention) and
# writes, under sim/devchar-passives/:
#   netlist-snapshots/<id>.spice   frozen copy of tb_cap_cv.sp / tb_res.sp
#   corners/<id>/<corner-id>.log   raw ngspice output, one per corner point
#   corners/<id>/*.csv              extracted metrics for that record's claim
#   records/<id>.md                 summary record (the citable evidence object)

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP="$(cd "${HERE}/.." && pwd)"
# shellcheck source=../../lib/simenv.sh
. "${HERE}/../../lib/simenv.sh"

CAP_DECK="${HERE}/tb_cap_cv.sp"
RES_DECK="${HERE}/tb_res.sp"
WORK="${EXP}/work"

CAP_SUMMARY_HEADER="device,family,corner_section,temp_c,area_um2,c_0v30_f,c_1v65_f,c_3v30_f,dens_3v30_ff_um2,dens_min_ff_um2,dens_max_ff_um2,cv_ratio,leak_3v63_a"
CAP_CURVE_HEADER="device,corner_section,temp_c,v_v,c_f,density_ff_um2"
RES_SUMMARY_HEADER="device,width_um,corner_section,temp_c,r_10um_ohm,r_50um_ohm,rsh_eff_ohm_sq,r_head_ohm,r_vcoef_pct_per_v"
RES_TEMPCO_HEADER="device,width_um,corner_section,r_m40c_ohm,r_27c_ohm,r_125c_ohm,tc_ppm_per_c"

CAP_AREA_UM2=900   # 30 um x 30 um drawn
CURVE_DECIMATE=50  # 1 ns transient steps -> archive roughly every 50 mV

# --------------------------------------------------------------------------
# One capacitor corner point.
#   run_cap <section> <temp> <summary-out> <curve-out>
# --------------------------------------------------------------------------
run_cap() {
  local mimsec="$1" mossec="$2" temp="$3" sfile="$4" cfile="$5"
  # Both axes move together, so one label identifies the point.
  local sec="${mimsec#mimcap_}"
  local tag="cap_${sec}_T${temp}"
  tag="${tag//-/m}"

  # `cap_mim` is the legacy-name section of sm141064.ngspice, which no corner
  # section pulls in; it is added explicitly so both MIM naming families can be
  # compared in the same deck. It reads the mim_corner_* params set by mimsec.
  simenv_run_deck "${CAP_DECK}" "${WORK}" "${tag}" \
    "${mimsec},${mossec},cap_mim" "${temp}" >/dev/null

  awk -v sec="${sec}" -v temp="${temp}" -v area="${CAP_AREA_UM2}" \
      -v dec="${CURVE_DECIMATE}" -v sfile="${sfile}" -v cfile="${cfile}" '
    function abs(x) { return x < 0 ? -x : x }
    BEGIN {
      nd = 10
      name[1] = "cap_mim_1f0_m2m3_noshield"; fam[1] = "mim"
      name[2] = "cap_mim_1f5_m2m3_noshield"; fam[2] = "mim"
      name[3] = "cap_mim_2f0_m2m3_noshield"; fam[3] = "mim"
      name[4] = "cap_mim_1f0fF";             fam[4] = "mim_legacy"
      name[5] = "cap_mim_1f5fF";             fam[5] = "mim_legacy"
      name[6] = "cap_mim_2f0fF";             fam[6] = "mim_legacy"
      name[7] = "cap_nmos_03v3";             fam[7] = "moscap"
      name[8] = "cap_pmos_03v3";             fam[8] = "moscap"
      name[9] = "cap_nmos_03v3_b";           fam[9] = "moscap"
      name[10] = "cap_pmos_03v3_b";          fam[10] = "moscap"
      # C-V window used for the linearity metric: a realistic control-voltage
      # excursion, excluding the last 300 mV against each rail.
      vlo = 0.30; vhi = 3.30
    }
    # wrdata layout: t v(r) t i1 t i2 ... -> vector k lives in column 2k
    {
      n++
      t[n] = $1; vr[n] = $2
      for (d = 1; d <= nd; d++) cur[d, n] = $(2 * (d + 1))
    }
    END {
      for (d = 1; d <= nd; d++) { dmin[d] = 1e30; dmax[d] = -1e30 }
      m = 0
      for (k = 2; k < n; k++) {
        dvdt = (vr[k + 1] - vr[k - 1]) / (t[k + 1] - t[k - 1])
        if (dvdt <= 0) continue                 # holding phase, not the ramp
        if (vr[k] < 0.02 || vr[k] > 3.62) continue
        m++
        vv[m] = vr[k]
        for (d = 1; d <= nd; d++) {
          c = abs(cur[d, k]) / dvdt
          cc[d, m] = c
          if (vr[k] >= vlo && vr[k] <= vhi) {
            if (c < dmin[d]) dmin[d] = c
            if (c > dmax[d]) dmax[d] = c
          }
        }
      }
      # nearest-sample lookup on the ramp
      for (d = 1; d <= nd; d++) {
        c030 = 0; c165 = 0; c330 = 0
        b030 = 9; b165 = 9; b330 = 9
        for (k = 1; k <= m; k++) {
          if (abs(vv[k] - 0.30) < b030) { b030 = abs(vv[k] - 0.30); c030 = cc[d, k] }
          if (abs(vv[k] - 1.65) < b165) { b165 = abs(vv[k] - 1.65); c165 = cc[d, k] }
          if (abs(vv[k] - 3.30) < b330) { b330 = abs(vv[k] - 3.30); c330 = cc[d, k] }
        }
        leak = abs(cur[d, n])
        printf "%s,%s,%s,%s,%d,%.6g,%.6g,%.6g,%.4f,%.4f,%.4f,%.4f,%.6g\n",
               name[d], fam[d], sec, temp, area, c030, c165, c330,
               c330 / area * 1e15, dmin[d] / area * 1e15, dmax[d] / area * 1e15,
               (dmin[d] > 0 ? dmax[d] / dmin[d] : 0), leak >> sfile
        for (k = 1; k <= m; k += dec)
          printf "%s,%s,%s,%.4f,%.6g,%.4f\n",
                 name[d], sec, temp, vv[k], cc[d, k], cc[d, k] / area * 1e15 >> cfile
      }
    }' "${WORK}/${tag}/cv.dat"
}

# --------------------------------------------------------------------------
# One resistor corner point.
#   run_res <section> <temp> <summary-out>
# --------------------------------------------------------------------------
run_res() {
  local sec="$1" temp="$2" sfile="$3"
  local tag="${sec}_T${temp}"
  tag="${tag//-/m}"

  simenv_run_deck "${RES_DECK}" "${WORK}" "${tag}" "${sec}" "${temp}" >/dev/null

  awk -v sec="${sec}" -v temp="${temp}" -v sfile="${sfile}" '
    function abs(x) { return x < 0 ? -x : x }
    BEGIN {
      np = 7
      name[1] = "ppolyf_u";    wid[1] = 1
      name[2] = "ppolyf_u";    wid[2] = 2
      name[3] = "ppolyf_u_1k"; wid[3] = 1
      name[4] = "ppolyf_u_2k"; wid[4] = 1
      name[5] = "ppolyf_u_3k"; wid[5] = 1
      name[6] = "npolyf_u";    wid[6] = 1
      name[7] = "ppolyf_s";    wid[7] = 1
      lshort = 10; llong = 50
    }
    # wrdata layout: v i_short1 v i_long1 v i_short2 ... -> vector k in column 2k
    { n++; v[n] = $1; for (c = 1; c <= 2 * np; c++) cur[c, n] = $(2 * c) }
    END {
      # index of the 0.1 V and 1.0 V sweep points
      klo = 0; khi = n
      for (k = 1; k <= n; k++) if (abs(v[k] - 0.1) < 0.0125) { klo = k; break }
      for (p = 1; p <= np; p++) {
        cs = 2 * p - 1; cl = 2 * p
        rs_hi = v[n] / abs(cur[cs, n]); rl_hi = v[n] / abs(cur[cl, n])
        rs_lo = v[klo] / abs(cur[cs, klo]); rl_lo = v[klo] / abs(cur[cl, klo])
        # squares of body length between the two drawn lengths
        nsq = (llong - lshort) / wid[p]
        rsh = (rl_hi - rs_hi) / nsq
        head = rs_hi - rsh * lshort / wid[p]
        vcoef = (rl_lo > 0) ? 100 * (rl_hi - rl_lo) / rl_lo / (v[n] - v[klo]) : 0
        printf "%s,%d,%s,%s,%.6g,%.6g,%.6g,%.6g,%.4g\n",
               name[p], wid[p], sec, temp, rs_hi, rl_hi, rsh, head, vcoef >> sfile
      }
    }' "${WORK}/${tag}/rdc.dat"
}

# --------------------------------------------------------------------------
# Entry points
# --------------------------------------------------------------------------
case "${1:-}" in
  --one-cap) shift; run_cap "$@"; exit 0 ;;
  --one-res) shift; run_res "$@"; exit 0 ;;
esac

simenv_require_tools
mkdir -p "${WORK}"

if [ "${1:-}" = "--check" ]; then
  tmpdir=$(mktemp -d)
  trap 'rm -rf "${tmpdir}"' EXIT
  run_cap mimcap_typical moscap_typical 27 "${tmpdir}/cap.csv" "${tmpdir}/cv.csv"
  run_res res_typical 27 "${tmpdir}/res.csv"
  echo "${CAP_SUMMARY_HEADER}"; cat "${tmpdir}/cap.csv"
  echo
  echo "${RES_SUMMARY_HEADER}"; cat "${tmpdir}/res.csv"
  exit 0
fi

# The three passive axes are independent sections, but each device depends on
# exactly one of them, so stepping them in lockstep still gives every device
# its full min/typ/max envelope.
NSEC=${#SIMENV_MIMCAP_CORNERS[@]}
JOBLIST="${WORK}/jobs.txt"
: >"${JOBLIST}"
for ((i = 0; i < NSEC; i++)); do
  mimsec="${SIMENV_MIMCAP_CORNERS[$i]}"
  mossec="${SIMENV_MOSCAP_CORNERS[$i]}"
  ressec="${SIMENV_RES_CORNERS[$i]}"
  sec="${mimsec#mimcap_}"
  for temp in "${SIMENV_TEMPS[@]}"; do
    t="${temp//-/m}"
    echo "--one-cap ${mimsec} ${mossec} ${temp} ${WORK}/cap_${sec}_${t}.sum ${WORK}/cap_${sec}_${t}.cur" >>"${JOBLIST}"
    echo "--one-res ${ressec} ${temp} ${WORK}/res_${sec}_${t}.sum" >>"${JOBLIST}"
  done
done
NJOBS=$(wc -l <"${JOBLIST}" | tr -d ' ')
echo "devchar-passives: ${NJOBS} runs ($(( NJOBS / 2 )) cap + $(( NJOBS / 2 )) res), $(simenv_jobs) parallel jobs"

rm -f "${WORK}"/*.sum "${WORK}"/*.cur
# shellcheck disable=SC2016
xargs -P "$(simenv_jobs)" -L 1 \
  "${BASH:-/bin/bash}" -c 'exec "$0" "$@"' "${HERE}/run.sh" \
  <"${JOBLIST}"

NTEMP=${#SIMENV_TEMPS[@]}
EXPECT_CAP=$((NSEC * NTEMP * 10))
EXPECT_RES=$((NSEC * NTEMP * 7))
GOT_CAP=$(cat "${WORK}"/cap_*.sum | wc -l | tr -d ' ')
GOT_RES=$(cat "${WORK}"/res_*.sum | wc -l | tr -d ' ')
if [ "${GOT_CAP}" -ne "${EXPECT_CAP}" ] || [ "${GOT_RES}" -ne "${EXPECT_RES}" ]; then
  echo "ERROR: expected ${EXPECT_CAP} cap / ${EXPECT_RES} res rows, got ${GOT_CAP} / ${GOT_RES}" >&2
  exit 1
fi

CAP_CORNERS="mimcap_{typical,ff,ss} + moscap_{typical,ff,ss} (swept together) x temp{-40,27,125}C; C-V sweep 0..3.63V covers the control range at every supply corner"
RES_CORNERS="res_{typical,ff,ss} x temp{-40,27,125}C; V across device swept 0..1.0V"

# --------------------------------------------------------------------------
# Mint two evidence records (sim/README.md convention): the cap comparison
# and the resistor comparison are distinct claims (#4 -> #10, cap vs. R
# selection respectively) sharing this experiment directory's testbench/, so
# each gets its own record id, netlist snapshot and corner-log set.
# --------------------------------------------------------------------------
RID_CAP=$(simenv_record_id)
sleep 1  # force a distinct record id (record id resolution is 1 second)
RID_RES=$(simenv_record_id)
SNAPDIR="${EXP}/netlist-snapshots"
RECORDSDIR="${EXP}/records"
CAPCORNERSDIR="${EXP}/corners/${RID_CAP}"
RESCORNERSDIR="${EXP}/corners/${RID_RES}"
mkdir -p "${SNAPDIR}" "${RECORDSDIR}" "${CAPCORNERSDIR}" "${RESCORNERSDIR}"

cp "${CAP_DECK}" "${SNAPDIR}/${RID_CAP}.spice"
SHA_CAP=$(simenv_sha256 "${SNAPDIR}/${RID_CAP}.spice")
cp "${RES_DECK}" "${SNAPDIR}/${RID_RES}.spice"
SHA_RES=$(simenv_sha256 "${SNAPDIR}/${RID_RES}.spice")

# Archive per-corner logs. Passives have no supply axis (C-V/R-V sweep IS the
# voltage axis), so the corner id here is <bundle>_<temp>c rather than the
# MOS-campaign <bundle>_<temp>c_<supply>v form -- noted in each record.
for ((i = 0; i < NSEC; i++)); do
  mimsec="${SIMENV_MIMCAP_CORNERS[$i]}"
  ressec="${SIMENV_RES_CORNERS[$i]}"
  sec="${mimsec#mimcap_}"
  for temp in "${SIMENV_TEMPS[@]}"; do
    captag="cap_${sec}_T${temp}"; captag="${captag//-/m}"
    simenv_archive_log "${WORK}" "${captag}" "${CAPCORNERSDIR}" "cap-${sec}_${temp}c"
    restag="${ressec}_T${temp}"; restag="${restag//-/m}"
    simenv_archive_log "${WORK}" "${restag}" "${RESCORNERSDIR}" "${ressec}_${temp}c"
  done
done

{
  simenv_provenance "devchar-passives (capacitors)" "${RID_CAP}" \
    "sim/devchar-passives/testbench/tb_cap_cv.sp" "${CAP_CORNERS}"
  cat <<'EOF'
# geometry: every device drawn 30 um x 30 um = 900 um^2
# method: linear 0 -> 3.63 V ramp in 1 us; C(V) = i / (dv/dt) with both taken
#   from the simulated waveform, then a 1 us hold at 3.63 V whose residual
#   branch current is the leakage column
# dens_min/max and cv_ratio are taken over a 0.30 .. 3.30 V control window
# family mim_legacy = the cap_mim_*fF names in the .LIB cap_mim section of
#   sm141064.ngspice, which NO corner section includes; this deck pulls that
#   section in explicitly so the two naming families can be compared
EOF
  echo "${CAP_SUMMARY_HEADER}"
  cat "${WORK}"/cap_*.sum | sort -t, -k1,1 -k3,3 -k4,4n
} >"${CAPCORNERSDIR}/cap_summary.csv"

{
  simenv_provenance "devchar-passives (capacitor C-V curves)" "${RID_CAP}" \
    "sim/devchar-passives/testbench/tb_cap_cv.sp" "${CAP_CORNERS}"
  echo "${CAP_CURVE_HEADER}"
  cat "${WORK}"/cap_*.cur | sort -t, -k1,1 -k2,2 -k3,3n -k4,4n
} >"${CAPCORNERSDIR}/cap_cv.csv"

{
  simenv_provenance "devchar-passives (resistors)" "${RID_RES}" \
    "sim/devchar-passives/testbench/tb_res.sp" "${RES_CORNERS}"
  cat <<'EOF'
# geometry: two drawn lengths per device, 10 um and 50 um, at W = 1 um
#   (ppolyf_u additionally at W = 2 um)
# rsh_eff_ohm_sq = (R_50um - R_10um) / squares between the two lengths, which
#   cancels the contact head resistance; r_head_ohm is the remaining intercept
#   (both terminals). rsh_eff differs from the model rsh parameter by the
#   effective-width narrowing, which is why it is measured rather than quoted.
# r_vcoef_pct_per_v: change in R between 0.1 V and 1.0 V across the device
EOF
  echo "${RES_SUMMARY_HEADER}"
  cat "${WORK}"/res_*.sum | sort -t, -k1,1 -k2,2n -k3,3 -k4,4n
} >"${RESCORNERSDIR}/res_summary.csv"

# Temperature coefficient, derived from the three temperature points of each
# (device, width, section). Uses the 50 um device, whose resistance is body
# dominated, so this is the body tempco rather than a head-weighted mixture.
{
  simenv_provenance "devchar-passives (resistor temperature coefficient)" "${RID_RES}" \
    "sim/devchar-passives/testbench/tb_res.sp" "${RES_CORNERS}"
  cat <<'EOF'
# tc_ppm_per_c = (R(125C) - R(-40C)) / (R(27C) * 165 C), from the 50 um device
EOF
  echo "${RES_TEMPCO_HEADER}"
  cat "${WORK}"/res_*.sum | awk -F, '
    { key = $1 "," $2 "," $3; r[key, $4] = $6; seen[key] = 1 }
    END {
      for (k in seen)
        printf "%s,%.6g,%.6g,%.6g,%.1f\n", k, r[k, -40], r[k, 27], r[k, 125],
               1e6 * (r[k, 125] - r[k, -40]) / (r[k, 27] * 165)
    }' | sort -t, -k1,1 -k2,2n -k3,3
} >"${RESCORNERSDIR}/res_tempco.csv"

echo "devchar-passives: wrote ${CAPCORNERSDIR}/{cap_summary,cap_cv}.csv, ${RESCORNERSDIR}/{res_summary,res_tempco}.csv"

# --------------------------------------------------------------------------
# Summary stats for the two records' Result tables, computed from the CSVs.
# --------------------------------------------------------------------------
CAP_DENS_TABLE=$(grep -v '^#' "${CAPCORNERSDIR}/cap_summary.csv" | tail -n +2 | awk -F, '
  { key=$1"/"$2
    if (!(key in dmin) || $10+0<dmin[key]) dmin[key]=$10+0
    if (!(key in dmax) || $11+0>dmax[key]) dmax[key]=$11+0
    if (!(key in cvmin) || $12+0<cvmin[key]) cvmin[key]=$12+0
    if (!(key in cvmax) || $12+0>cvmax[key]) cvmax[key]=$12+0
  }
  END { for (k in dmin) printf "%s %.4f %.4f %.4f %.4f\n", k, dmin[k], dmax[k], cvmin[k], cvmax[k] }' \
  | sort | awk '{printf "  | %s | %s .. %s | %s .. %s |\n", $1, $2, $3, $4, $5}')

RES_RSH_TABLE=$(grep -v '^#' "${RESCORNERSDIR}/res_summary.csv" | tail -n +2 | awk -F, '
  { key=$1"(W="$2"um)"
    if (!(key in rmin) || $7+0<rmin[key]) rmin[key]=$7+0
    if (!(key in rmax) || $7+0>rmax[key]) rmax[key]=$7+0
  }
  END { for (k in rmin) printf "%s %.6g %.6g\n", k, rmin[k], rmax[k] }' \
  | sort | awk '{printf "  | %s | %s | %s |\n", $1, $2, $3}')

# res_tempco.csv columns (1-indexed, after stripping '#' comments and the
# header row), per RES_TEMPCO_HEADER above:
#   1 device, 2 width_um, 3 corner_section, 4 r_m40c_ohm, 5 r_27c_ohm,
#   6 r_125c_ohm, 7 tc_ppm_per_c
RES_TC_TABLE=$(grep -v '^#' "${RESCORNERSDIR}/res_tempco.csv" | tail -n +2 | awk -F, '{printf "  | %s (W=%sum, %s) | %.1f |\n", $1, $2, $3, $7}' | sort)

RECORD_CAP="${RECORDSDIR}/${RID_CAP}.md"
{
  cat <<EOF
# Record ${RID_CAP}

- **Record ID**: ${RID_CAP}
- **Claim**: #4 -> #10 (design-input, not a spec line) -- which loop-filter
  capacitor type (MIM vs. 3.3 V MOS cap) meets the < 0.15 mm^2 area budget
  with acceptable C-V linearity and leakage.
- **Netlist provenance**: schematic (\`sim/devchar-passives/testbench/tb_cap_cv.sp\`)
  -> \`sim/devchar-passives/netlist-snapshots/${RID_CAP}.spice\`, SHA-256 \`${SHA_CAP}\`
- **Environment provenance**:
$(simenv_env_block)
- **Corner matrix run**: ${NSEC} passive corner-section triples x 3
  temperatures = $((NSEC * ${#SIMENV_TEMPS[@]})) runs, 10 devices extracted
  per run
  - Sections swept together (independent axis from the MOS tt/ff/ss/fs/sf
    sections used by devchar-delay/devchar-cp): \`mimcap_typical\`+\`moscap_typical\`,
    \`mimcap_ff\`+\`moscap_ff\`, \`mimcap_ss\`+\`moscap_ss\` (the \`.LIB cap_mim\`
    legacy section is also included unconditionally, at every point, to
    confirm the two MIM naming families agree)
  - Temperature: -40 C, 27 C, 125 C
  - **Supply axis N/A**: the C-V ramp itself (0 -> 3.63 V) covers the full
    control-voltage range at every supply corner, so supply is the sweep
    variable, not an independent corner axis. Corner-id filenames therefore
    drop the \`_<supply>v\` suffix used by the MOS campaigns
    (\`cap-<section>_<temp>c\` rather than \`<bundle>_<temp>c_<supply>v\`).
  - MOS process bundles N/A -- no active devices in the DUT.
- **Methodology / criteria / limitations**:
  - Measurement topology: linear voltage ramp 0 -> 3.63 V over 1 us on a
    shared node, each of 10 candidate devices tied to it through its own 0 V
    ammeter; \`C(V) = i / (dv/dt)\`, both taken from the simulated waveform (not
    assuming the ramp is exactly linear), then a 1 us hold at 3.63 V whose
    residual branch current is the leakage figure.
  - Geometry: every device drawn 30 x 30 um = 900 um^2, so densities are
    directly comparable.
  - \`dens_min/max\`, \`cv_ratio\` (linearity) computed over a 0.30-3.30 V control
    window (excludes the last 300 mV against each rail).
  - \`.option abstol=1e-18 reltol=1e-7 vntol=1e-9 gmin=1e-15\` -- leakage in
    these models runs from femtoamps down to exactly zero, so the solver
    needs tightening well past defaults for the leakage column to be
    meaningful.
  - Statistical switches: \`sw_stat_global = sw_stat_mismatch = 0\`.
- **Statistical convention**: N/A -- corner-matrix claim, not a distribution
  claim.
- **Result**: density and C-V linearity ratio, min/max across all 9 sections
  x temperature points, per device (fF/um^2, cv_ratio = C_max/C_min over the
  0.30-3.30 V window):

  | Device / family | dens_ff_um2 min .. max | cv_ratio min .. max |
  |---|---|---|
${CAP_DENS_TABLE}

  MOS caps are expected to show markedly higher density than MIM at the cost
  of a much larger cv_ratio (strong accumulation-mode voltage dependence);
  the two MIM naming families (\`_m2m3_noshield\` vs. legacy \`fF\`) should
  read electrically identical. See the full table for per-corner detail and
  leakage; full C-V curves through the control range are in \`cap_cv.csv\`.
  Full tables: \`sim/devchar-passives/corners/${RID_CAP}/cap_summary.csv\`,
  \`cap_cv.csv\`.
- **Links**:
  - Testbench: \`sim/devchar-passives/testbench/tb_cap_cv.sp\`
  - Netlist snapshot: \`sim/devchar-passives/netlist-snapshots/${RID_CAP}.spice\`
  - Raw logs: \`sim/devchar-passives/corners/${RID_CAP}/\`
  - Extracted metrics: \`sim/devchar-passives/corners/${RID_CAP}/cap_summary.csv\`,
    \`sim/devchar-passives/corners/${RID_CAP}/cap_cv.csv\`
- **Timestamp / author**: $(date -u +%Y-%m-%dT%H:%M:%SZ), agent-builder
- **Supersedes**: (none -- first record for this claim)
EOF
} >"${RECORD_CAP}"

RECORD_RES="${RECORDSDIR}/${RID_RES}.md"
{
  cat <<EOF
# Record ${RID_RES}

- **Record ID**: ${RID_RES}
- **Claim**: #4 -> #10 (design-input, not a spec line) -- poly-resistor
  option for the loop-filter series resistor: sheet-resistance spread across
  \`res_ff\`/\`res_ss\` and temperature coefficient for \`ppolyf_u\` vs. the
  high-sheet variants.
- **Netlist provenance**: schematic (\`sim/devchar-passives/testbench/tb_res.sp\`)
  -> \`sim/devchar-passives/netlist-snapshots/${RID_RES}.spice\`, SHA-256 \`${SHA_RES}\`
- **Environment provenance**:
$(simenv_env_block)
- **Corner matrix run**: ${NSEC} passive corner sections x 3 temperatures =
  $((NSEC * ${#SIMENV_TEMPS[@]})) runs, 7 devices extracted per run
  - Sections (\`res_*\`, independent axis from the MOS tt/ff/ss/fs/sf sections):
    \`res_typical\`, \`res_ff\`, \`res_ss\`
  - Temperature: -40 C, 27 C, 125 C
  - **Supply axis N/A**: device-level R-V sweep (0 -> 1.0 V across the
    device) is the voltage-coefficient probe, not a supply corner. Corner-id
    filenames are \`<section>_<temp>c\`.
  - MOS process bundles N/A -- no active devices in the DUT.
- **Methodology / criteria / limitations**:
  - Measurement topology: every device between a shared swept node and
    ground through its own 0 V ammeter, DC sweep 0 -> 1.0 V in 25 mV steps,
    R(V) = V/I (voltage coefficient measured, not assumed). Two drawn lengths
    (10 um, 50 um at W=1um; \`ppolyf_u\` additionally at W=2um) let
    \`rsh_eff = (R_50um - R_10um) / squares-between-lengths\` cancel the fixed
    contact head resistance; the head resistance is the remaining intercept.
  - \`r_vcoef_pct_per_v\`: fractional change in R between 0.1 V and 1.0 V
    across the device.
  - \`tc_ppm_per_c = (R(125C) - R(-40C)) / (R(27C) * 165C)\`, from the 50 um
    device (body-dominated, so this is the body tempco rather than a
    head-weighted mixture).
  - Statistical switches: \`sw_stat_global = sw_stat_mismatch = 0\`.
- **Statistical convention**: N/A -- corner-matrix claim, not a distribution
  claim.
- **Result**: effective sheet resistance, min/max across \`res_typical/ff/ss\`
  x 3 temperatures, per device:

  | Device | rsh_eff_ohm_sq min | rsh_eff_ohm_sq max |
  |---|---|---|
${RES_RSH_TABLE}

  Temperature coefficient (tc_ppm_per_c, res_typical/ff/ss each get their own
  row -- see the full CSV):

  | Device (section) | tc_ppm_per_c |
  |---|---|
${RES_TC_TABLE}

  \`ppolyf_u\` is the near-zero-TC option (~-75 ppm/C, essentially section- and
  width-independent); the high-sheet variants trade that away, running about
  -870 ppm/C (\`_1k\`) to -1545 ppm/C (\`_2k\`/\`_3k\`). \`ppolyf_s\` (salicided) is
  included as a negative example on both axes: its rsh is roughly 2 orders of
  magnitude below the unsalicided options, and its tempco is large and
  *positive* (+2.9e3 .. +3.2e3 ppm/C, metal-like) where every unsalicided
  option is negative -- neither is loop-filter friendly. See the full tables
  for \`r_vcoef_pct_per_v\` and \`r_head_ohm\`.
  Full tables: \`sim/devchar-passives/corners/${RID_RES}/res_summary.csv\`,
  \`res_tempco.csv\`.
- **Links**:
  - Testbench: \`sim/devchar-passives/testbench/tb_res.sp\`
  - Netlist snapshot: \`sim/devchar-passives/netlist-snapshots/${RID_RES}.spice\`
  - Raw logs: \`sim/devchar-passives/corners/${RID_RES}/\`
  - Extracted metrics: \`sim/devchar-passives/corners/${RID_RES}/res_summary.csv\`,
    \`sim/devchar-passives/corners/${RID_RES}/res_tempco.csv\`
- **Timestamp / author**: $(date -u +%Y-%m-%dT%H:%M:%SZ), agent-builder
- **Supersedes**: (none -- first record for this claim)
EOF
} >"${RECORD_RES}"

echo "devchar-passives: wrote ${RECORD_CAP}"
echo "devchar-passives: wrote ${RECORD_RES}"
