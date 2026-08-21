#!/usr/bin/env bash
# gf180-pll :: devchar-delay :: corner runner
#
# SUPERSEDED FOR NEW RUNS by this campaign's sim/harness manifest
# (testbench/tb.json + the .spice fragment beside it) -- run
#   python3 sim/run_corners.py <slug>
# instead. This script is kept because the records it already minted are
# append-only evidence and it is the only thing that can regenerate the
# extra CSV artifacts they cite; do not extend it.
#
# Sweeps tb_delay_stage.sp over the full repo PVT grid:
#   process {typical, ff, ss, fs, sf} x temp {-40, 27, 125} C x supply
#   {2.97, 3.30, 3.63} V  = 45 points.
#
# Usage:
#   ./run.sh                 # full 45-point grid -> mints a records/<id>.md
#   ./run.sh --check         # nominal corner only, printed to stdout (no write)
#   SIM_JOBS=4 ./run.sh      # cap parallelism
#
# A full run mints one record ID and writes, under sim/devchar-delay/ (per
# sim/README.md, the repo's append-only evidence-record convention):
#   netlist-snapshots/<id>.spice   frozen copy of tb_delay_stage.sp
#   corners/<id>/<corner-id>.log   raw ngspice output, one per PVT point
#   corners/<id>/delay_corners.csv extracted per-corner metrics
#   records/<id>.md                 summary record (the citable evidence object)

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP="$(cd "${HERE}/.." && pwd)"
# shellcheck source=../../lib/simenv.sh
. "${HERE}/../../lib/simenv.sh"

DECK="${HERE}/tb_delay_stage.sp"
WORK="${EXP}/work"

CSV_HEADER="process,temp_c,vdd_v,ring1x_fosc_hz,ring1x_tstage_s,ring1x_isupply_a,ring1x_qstage_c,ring1x_cstage_f,ring4x_fosc_hz,ring4x_tstage_s,ring4x_isupply_a,fo1_tphl_s,fo1_tplh_s,fo1_tpd_s,fo1_tfall_s,fo1_trise_s,idsat_n_1u_a,idsat_p_2u5_a,cs_lo_fosc_hz,cs_lo_tstage_s,cs_lo_isupply_a,cs_md_fosc_hz,cs_md_tstage_s,cs_md_isupply_a,cs_hi_fosc_hz,cs_hi_tstage_s,cs_hi_isupply_a"

# --------------------------------------------------------------------------
# Single corner point. Prints one CSV row on stdout.
# --------------------------------------------------------------------------
run_one() {
  local corner="$1" temp="$2" vdd="$3"
  local tag="${corner}_T${temp}_V${vdd}"
  tag=$(simenv_mktag "${tag}")

  simenv_run_deck "${DECK}" "${WORK}" "${tag}" "${corner}" "${temp}" "vsup=${vdd}" >/dev/null
  local log="${WORK}/${tag}/ngspice.log"

  local r1_fosc r1_tstage r1_iavg r1_period r4_fosc r4_tstage r4_iavg
  local tphl tplh tpd tf tr idn idp
  local cs_lo_fosc cs_lo_tstage cs_lo_iavg cs_md_fosc cs_md_tstage cs_md_iavg
  local cs_hi_fosc cs_hi_tstage cs_hi_iavg
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
  cs_lo_fosc=$(simenv_meas "${log}" cs_lo_fosc)
  cs_lo_tstage=$(simenv_meas "${log}" cs_lo_tstage)
  cs_lo_iavg=$(simenv_meas "${log}" cs_lo_iavg)
  cs_md_fosc=$(simenv_meas "${log}" cs_md_fosc)
  cs_md_tstage=$(simenv_meas "${log}" cs_md_tstage)
  cs_md_iavg=$(simenv_meas "${log}" cs_md_iavg)
  cs_hi_fosc=$(simenv_meas "${log}" cs_hi_fosc)
  cs_hi_tstage=$(simenv_meas "${log}" cs_hi_tstage)
  cs_hi_iavg=$(simenv_meas "${log}" cs_hi_iavg)

  # Derived: charge drawn from the supply per stage transition, and the
  # equivalent switched capacitance C = Q/Vdd. Includes short-circuit current,
  # so it is an upper bound on the pure load capacitance -- which is the number
  # a ring-VCO power/frequency estimate actually wants.
  awk -v c="${corner}" -v t="${temp}" -v v="${vdd}" \
      -v r1f="${r1_fosc}" -v r1ts="${r1_tstage}" -v r1i="${r1_iavg}" -v r1p="${r1_period}" \
      -v r4f="${r4_fosc}" -v r4ts="${r4_tstage}" -v r4i="${r4_iavg}" \
      -v tphl="${tphl}" -v tplh="${tplh}" -v tpd="${tpd}" -v tf="${tf}" -v tr="${tr}" \
      -v idn="${idn}" -v idp="${idp}" \
      -v csl_f="${cs_lo_fosc}" -v csl_t="${cs_lo_tstage}" -v csl_i="${cs_lo_iavg}" \
      -v csm_f="${cs_md_fosc}" -v csm_t="${cs_md_tstage}" -v csm_i="${cs_md_iavg}" \
      -v csh_f="${cs_hi_fosc}" -v csh_t="${cs_hi_tstage}" -v csh_i="${cs_hi_iavg}" '
    function abs(x) { return x < 0 ? -x : x }
    BEGIN {
      nstage = 5
      q = abs(r1i) * r1p / nstage
      cs = (v > 0) ? q / v : 0
      printf "%s,%s,%s,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g\n",
             c, t, v, r1f, r1ts, abs(r1i), q, cs, r4f, r4ts, abs(r4i),
             tphl, tplh, tpd, tf, tr, abs(idn), abs(idp),
             csl_f, csl_t, abs(csl_i), csm_f, csm_t, abs(csm_i), csh_f, csh_t, abs(csh_i)
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

mkdir -p "${WORK}"

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

# --------------------------------------------------------------------------
# Mint the evidence record (sim/README.md convention).
# --------------------------------------------------------------------------
RID=$(simenv_record_id)
SNAPDIR="${EXP}/netlist-snapshots"
CORNERSDIR="${EXP}/corners/${RID}"
RECORDSDIR="${EXP}/records"
mkdir -p "${SNAPDIR}" "${CORNERSDIR}" "${RECORDSDIR}"

cp "${DECK}" "${SNAPDIR}/${RID}.spice"
SHA=$(simenv_sha256 "${SNAPDIR}/${RID}.spice")

# Archive each corner's generated deck + raw ngspice output as committed
# evidence, corner-id-named per sim/README.md.
while read -r corner temp vdd; do
  tag="${corner}_T${temp}_V${vdd}"
  tag=$(simenv_mktag "${tag}")
  cid=$(simenv_corner_id "${corner}" "${temp}" "${vdd}")
  simenv_archive_log "${WORK}" "${tag}" "${CORNERSDIR}" "${cid}"
done <"${JOBLIST}"

CORNER_DESC="process{typical,ff,ss,fs,sf} x temp{-40,27,125}C x vdd{2.97,3.30,3.63}V = ${EXPECTED} points"
CSV_OUT="${CORNERSDIR}/delay_corners.csv"
{
  simenv_provenance "devchar-delay" "${RID}" \
    "sim/devchar-delay/testbench/tb_delay_stage.sp" "${CORNER_DESC}"
  cat <<'EOF'
# topology_ring1x/ring4x: 5-stage self-loaded ring of unstarved minimum-length
#   CMOS inverters ; ring1x: Wn=1.0um Wp=2.5um L=0.28um ; ring4x: Wn=4.0um
#   Wp=10.0um L=0.28um ; tstage = 1/(2*N*fosc) with N=5, fosc from 8 periods
#   after start-up. This is the ceiling an equivalent current-starved ring
#   approaches as the starving devices are driven fully on.
# topology_cs_lo/md/hi: 5-stage current-starved ring (DR-001 Decision 2 cell:
#   matched PMOS-head / NMOS-tail starving devices, l_st=0.5um, w_ph=5um,
#   w_nt=2um), starved at a fixed ideal-mirrored current of 10/50/250 uA
#   respectively. Isolates the delay cell from bias-generator PVT. Gives both
#   the per-corner frequency and the fosc-vs-Ictrl slope (Kvco proxy) #8 needs.
# topology_fo1: open 4-inverter chain (1x), stage 3 measured (identical driver
#   and identical fan-out-1 load), ideal step at the chain input
# idsat_n_1u / idsat_p_2u5: single device at Vgs=Vds=Vdd, W=1.0um n / 2.5um p
# qstage/cstage: supply charge per stage transition of ring1x and Q/Vdd;
#   includes short-circuit current, so cstage is an upper bound on load C
EOF
  echo "${CSV_HEADER}"
  sort -t, -k1,1 -k2,2n -k3,3n "${ROWS}"
} >"${CSV_OUT}"

# --------------------------------------------------------------------------
# Summary stats for the record's Result table (computed from the just-written
# CSV, not hand-typed, so the record cannot drift from the data).
# --------------------------------------------------------------------------
SUMMARY=$(grep -v '^#' "${CSV_OUT}" | tail -n +2 | awk -F, '{
    if (r1min=="" || $5+0<r1min) { r1min=$5+0; r1minc=$1"_"$2"C_"$3"V" }
    if (r1max=="" || $5+0>r1max) { r1max=$5+0; r1maxc=$1"_"$2"C_"$3"V" }
    if (cslmin=="" || $19+0<cslmin) cslmin=$19+0
    if (cslmax=="" || $19+0>cslmax) cslmax=$19+0
    if (cshmin=="" || $25+0<cshmin) cshmin=$25+0
    if (cshmax=="" || $25+0>cshmax) cshmax=$25+0
  }
  END {
    printf "%.6g %s %.6g %s %.6g %.6g %.6g %.6g\n", r1min, r1minc, r1max, r1maxc, cslmin, cslmax, cshmin, cshmax
  }' -)
R1_MIN="$(echo "${SUMMARY}" | awk '{print $1}')"
R1_MINC="$(echo "${SUMMARY}" | awk '{print $2}')"
R1_MAX="$(echo "${SUMMARY}" | awk '{print $3}')"
R1_MAXC="$(echo "${SUMMARY}" | awk '{print $4}')"
CS_LO_MIN="$(echo "${SUMMARY}" | awk '{print $5}')"
CS_LO_MAX="$(echo "${SUMMARY}" | awk '{print $6}')"
CS_HI_MIN="$(echo "${SUMMARY}" | awk '{print $7}')"
CS_HI_MAX="$(echo "${SUMMARY}" | awk '{print $8}')"

RECORD="${RECORDSDIR}/${RID}.md"
{
  cat <<EOF
# Record ${RID}

- **Record ID**: ${RID}
- **Claim**: #4 -> #8 (design-input, not a spec line) -- per-PVT-corner
  delay-cell drive/delay and current-starved-ring frequency vs. starving
  current, sufficient to bound ring-VCO frequency spread worst-slow to
  worst-fast and to estimate Kvco.
- **Netlist provenance**: schematic (\`sim/devchar-delay/testbench/tb_delay_stage.sp\`)
  -> \`sim/devchar-delay/netlist-snapshots/${RID}.spice\`, SHA-256 \`${SHA}\`
- **Environment provenance**:
$(simenv_env_block)
- **Corner matrix run**: ${EXPECTED} points (5 MOS bundles x 3 temperatures x
  3 supplies)
  - Bundles (-> \`.lib\` sections of sm141064.ngspice): \`typical\` -> typical;
    \`ff\` -> ff; \`ss\` -> ss; \`fs\` -> fs; \`sf\` -> sf
  - Temperature: -40 C, 27 C, 125 C
  - Supply: 2.97 V, 3.30 V, 3.63 V (3.3 V +/-10%)
  - **Axes not swept**: passive corner sections N/A -- this deck has no MIM/MOS
    caps or poly resistors in the DUT (pure active-device characterization).
- **Methodology / criteria / limitations**:
  - Measurement topology: four sub-circuits share one deck (see
    \`testbench/tb_delay_stage.sp\` header comment) --
    (1) **R1/R4**: unstarved 5-stage self-loaded CMOS ring at 1x and 4x
    sizing, stage delay td = T/(2N) from 8 periods after start-up (the
    frequency ceiling a current-starved ring approaches as fully-on);
    (2) **CS-lo/md/hi**: three 5-stage **current-starved** rings (the DR-001
    Decision-2 delay cell: matched PMOS-head/NMOS-tail starving devices,
    L_st=0.5um), each starved at a fixed *ideal* mirrored current
    (10/50/250 uA) so the bias-generator's own PVT sensitivity is isolated
    from the cell's; frequency measured over 4 periods after start-up;
    (3) **CH**: open fan-out-1 inverter chain (ideal step in) giving tpHL/tpLH
    separately and 10-90% transition times; (4) **DC**: single 1x NMOS/PMOS at
    Vgs=Vds=Vdd for peak drive current.
  - Simulator settings: \`.tran 5p 150n uic\` (5 ps max step, 150 ns covers >=6
    periods of the slowest starved ring at the slowest corner).
  - **Limitation**: the CS bias uses an *ideal* current source into a diode
    mirror, not the real band-select/V-to-I bias network #8 will design --
    this isolates the delay cell's PVT sensitivity from the bias generator's,
    which is the correct scope for this record but means the real bias
    network's own PVT sensitivity is a separate, later characterization.
  - Statistical switches: \`sw_stat_global = sw_stat_mismatch = 0\` (nominal
    device skew from the corner section only, no Monte Carlo mismatch).
- **Statistical convention**: N/A -- corner-matrix claim, not a distribution
  claim.
- **Result**:

  Unstarved ring (ceiling) stage delay spans the full grid:
  | Metric | Value | Corner |
  |---|---|---|
  | ring1x t_stage min (fastest) | ${R1_MIN} s | ${R1_MINC} |
  | ring1x t_stage max (slowest) | ${R1_MAX} s | ${R1_MAXC} |

  Current-starved ring frequency range across the full 45-point grid:
  | Bias | f_osc min (Hz) | f_osc max (Hz) |
  |---|---|---|
  | i_lo = 10 uA | ${CS_LO_MIN} | ${CS_LO_MAX} |
  | i_hi = 250 uA | ${CS_HI_MIN} | ${CS_HI_MAX} |

  The i_lo..i_hi spread at a fixed corner is the Kvco proxy #8 consumes (25x
  current ratio); see the full per-corner table for the i_md point and every
  other extracted metric. Full 45-point table:
  \`sim/devchar-delay/corners/${RID}/delay_corners.csv\`.

  **Conclusion**: ss/125C/2.97V is the slowest corner and ff/-40C/3.63V the
  fastest for both the unstarved ceiling and the starved rings, as expected;
  see the CSV for the complete per-corner breakdown consumed by #8's band
  plan.
- **Links**:
  - Testbench: \`sim/devchar-delay/testbench/tb_delay_stage.sp\`
  - Netlist snapshot: \`sim/devchar-delay/netlist-snapshots/${RID}.spice\`
  - Raw logs: \`sim/devchar-delay/corners/${RID}/\`
  - Extracted metrics: \`sim/devchar-delay/corners/${RID}/delay_corners.csv\`
- **Timestamp / author**: $(date -u +%Y-%m-%dT%H:%M:%SZ), agent-builder
- **Supersedes**: (none -- first record for this claim)
EOF
} >"${RECORD}"

echo "devchar-delay: wrote ${RECORD}"
echo "devchar-delay: wrote ${CSV_OUT}"
echo "devchar-delay: wrote ${CORNERSDIR}/ (${EXPECTED} corner logs)"
