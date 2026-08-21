#!/usr/bin/env bash
# gf180-pll :: devchar-cp :: corner runner
#
# SUPERSEDED FOR NEW RUNS by this campaign's sim/harness manifest
# (testbench/tb.json + the .spice fragment beside it) -- run
#   python3 sim/run_corners.py <slug>
# instead. This script is kept because the records it already minted are
# append-only evidence and it is the only thing that can regenerate the
# extra CSV artifacts they cite; do not extend it.
#
# Sweeps tb_cp_mirror.sp over the full repo PVT grid:
#   process {typical, ff, ss, fs, sf} x temp {-40, 27, 125} C x supply
#   {2.97, 3.30, 3.63} V  = 45 points, six candidate mirror stacks per point.
#
# Usage:
#   ./run.sh                 # full grid -> mints a records/<id>.md (see below)
#   ./run.sh --check         # nominal corner only, summary printed to stdout
#   SIM_JOBS=4 ./run.sh      # cap parallelism
#
# A full run mints one record ID and writes, under sim/devchar-cp/ (per
# sim/README.md, the repo's append-only evidence-record convention):
#   netlist-snapshots/<id>.spice   frozen copy of tb_cp_mirror.sp
#   corners/<id>/<corner-id>.log   raw ngspice output, one per PVT point
#   corners/<id>/cp_summary.csv    extracted per-corner-per-stack metrics
#   corners/<id>/cp_curves.csv     decimated per-stack output I-V curves
#   records/<id>.md                 summary record (the citable evidence object)
#
# Extraction (all from the DC output I-V of each stack, 10 mV steps):
#   isat            deep-saturation output current (N: at Vout=Vdd, P: at Vout=0)
#   ro(Vout)        central difference dVout/dIout on the 10 mV grid
#   vcomp_i1pct     output voltage at which |Iout| first reaches 99 % of isat
#   vcomp_ro50      output voltage at which ro falls to 50 % of its mid-rail
#                   value -- the boundary that actually matters for a cascode,
#                   whose current stays accurate well past the point where its
#                   output resistance has collapsed
#   headroom_*      the same boundary expressed as distance from the stack's own
#                   rail (ground for the N sinks, Vdd for the P sources)

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP="$(cd "${HERE}/.." && pwd)"
# shellcheck source=../../lib/simenv.sh
. "${HERE}/../../lib/simenv.sh"

DECK="${HERE}/tb_cp_mirror.sp"
WORK="${EXP}/work"

SUMMARY_HEADER="stack,process,temp_c,vdd_v,iref_a,isat_a,iout_mid_a,gain_mid,ro_30pct_ohm,ro_50pct_ohm,ro_70pct_ohm,vcomp_i1pct_v,vcomp_i5pct_v,vcomp_ro50_v,headroom_i1pct_v,headroom_ro50_v,vth_ref_v,vdsat_ref_v"
CURVES_HEADER="stack,process,temp_c,vdd_v,vout_v,iout_a,ro_ohm"

IREF="20e-6"
# Decimation of the committed curve file: the sweep runs at 10 mV, the archived
# curve is every 5th point (50 mV), which still resolves every knee here.
CURVE_DECIMATE=5

# --------------------------------------------------------------------------
# Single corner point.
#   run_one <corner> <temp> <vdd> <summary-out> <curves-out>
# --------------------------------------------------------------------------
run_one() {
  local corner="$1" temp="$2" vdd="$3" sfile="$4" cfile="$5"
  local tag="${corner}_T${temp}_V${vdd}"
  tag=$(simenv_mktag "${tag}")

  simenv_run_deck "${DECK}" "${WORK}" "${tag}" "${corner}" "${temp}" "vsup=${vdd}" >/dev/null
  local rundir="${WORK}/${tag}"

  local opn opp
  opn=$(awk '/^OPN /{print $3" "$5; exit}' "${rundir}/ngspice.log")
  opp=$(awk '/^OPP /{print $3" "$5; exit}' "${rundir}/ngspice.log")
  if [ -z "${opn}" ] || [ -z "${opp}" ]; then
    echo "ERROR: missing operating-point record for tag=${tag}" >&2
    return 1
  fi

  awk -v corner="${corner}" -v temp="${temp}" -v vdd="${vdd}" -v iref="${IREF}" \
      -v opn="${opn}" -v opp="${opp}" -v dec="${CURVE_DECIMATE}" \
      -v sfile="${sfile}" -v cfile="${cfile}" '
    function abs(x) { return x < 0 ? -x : x }
    # nearest-index lookup on the (uniform) voltage grid
    function at(target,   k) { k = int(target / dv + 0.5) + 1; if (k < 1) k = 1; if (k > n) k = n; return k }
    BEGIN {
      split(opn, a, " "); vth["n"] = a[1]; vdsat["n"] = a[2]
      split(opp, b, " "); vth["p"] = b[1]; vdsat["p"] = b[2]
      nstack = 6
      name[1] = "n_simple"; name[2] = "n_casc"; name[3] = "n_ws"
      name[4] = "p_simple"; name[5] = "p_casc"; name[6] = "p_ws"
      pol[1] = "n"; pol[2] = "n"; pol[3] = "n"
      pol[4] = "p"; pol[5] = "p"; pol[6] = "p"
    }
    # wrdata interleaves the sweep scale with every vector: v i1 v i2 ... v i6
    {
      n++
      v[n] = $1
      for (s = 1; s <= nstack; s++) cur[s, n] = $(2 * s)
    }
    END {
      if (n < 10) { print "ERROR: short sweep" > "/dev/stderr"; exit 1 }
      dv = (v[n] - v[1]) / (n - 1)

      for (s = 1; s <= nstack; s++) {
        # --- output resistance, central difference on the raw grid
        for (k = 2; k < n; k++) {
          di = cur[s, k + 1] - cur[s, k - 1]
          ro[k] = (di == 0) ? 1e15 : abs((v[k + 1] - v[k - 1]) / di)
        }
        ro[1] = ro[2]; ro[n] = ro[n - 1]

        kmid = at(0.5 * vdd)
        romid = ro[kmid]
        iout_mid = abs(cur[s, kmid])

        # Compliance is referenced to the current the stack delivers at its
        # nominal operating point (mid-rail), NOT to the extreme-Vout value:
        # a simple mirror never stops climbing with Vout, so a "99 % of the
        # value at the rail" definition would report a meaningless number.
        # Walk from mid-rail toward the rail this stack works against, and stop
        # at the first point that leaves the +/-1 % (resp. +/-5 %) band.
        isat = iout_mid
        if (pol[s] == "n") {
          vc1 = v[1]; for (k = kmid; k >= 1; k--) if (abs(abs(cur[s, k]) - isat) > 0.01 * isat) { vc1 = v[k + 1]; break }
          vc5 = v[1]; for (k = kmid; k >= 1; k--) if (abs(abs(cur[s, k]) - isat) > 0.05 * isat) { vc5 = v[k + 1]; break }
          # small-signal compliance: walk down from mid-rail to the first point
          # where ro has fallen below half its mid-rail value
          vro = v[1]; for (k = kmid; k >= 1; k--) if (ro[k] < 0.5 * romid) { vro = v[k]; break }
          hd1 = vc1; hdro = vro
        } else {
          vc1 = v[n]; for (k = kmid; k <= n; k++) if (abs(abs(cur[s, k]) - isat) > 0.01 * isat) { vc1 = v[k - 1]; break }
          vc5 = v[n]; for (k = kmid; k <= n; k++) if (abs(abs(cur[s, k]) - isat) > 0.05 * isat) { vc5 = v[k - 1]; break }
          vro = v[n]; for (k = kmid; k <= n; k++) if (ro[k] < 0.5 * romid) { vro = v[k]; break }
          hd1 = vdd - vc1; hdro = vdd - vro
        }

        printf "%s,%s,%s,%s,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.4f,%.4f,%.4f,%.4f,%.4f,%.6g,%.6g\n",
               name[s], corner, temp, vdd, iref, (pol[s] == "n" ? abs(cur[s, n]) : abs(cur[s, 1])),
               iout_mid, iout_mid / iref,
               ro[at(0.3 * vdd)], romid, ro[at(0.7 * vdd)],
               vc1, vc5, vro, hd1, hdro, vth[pol[s]], vdsat[pol[s]] >> sfile

        for (k = 1; k <= n; k += dec)
          printf "%s,%s,%s,%s,%.4f,%.6g,%.6g\n",
                 name[s], corner, temp, vdd, v[k], abs(cur[s, k]), ro[k] >> cfile
      }
    }' "${rundir}/iv.dat"
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
mkdir -p "${WORK}"

if [ "${1:-}" = "--check" ]; then
  tmpdir=$(mktemp -d)
  trap 'rm -rf "${tmpdir}"' EXIT
  run_one typical 27 3.30 "${tmpdir}/s.csv" "${tmpdir}/c.csv"
  echo "${SUMMARY_HEADER}"
  cat "${tmpdir}/s.csv"
  exit 0
fi

JOBLIST="${WORK}/jobs.txt"
: >"${JOBLIST}"
for corner in "${SIMENV_MOS_CORNERS[@]}"; do
  for temp in "${SIMENV_TEMPS[@]}"; do
    for vdd in "${SIMENV_VDDS[@]}"; do
      tag="${corner}_T${temp}_V${vdd}"
      tag=$(simenv_mktag "${tag}")
      echo "${corner} ${temp} ${vdd} ${WORK}/${tag}.sum ${WORK}/${tag}.cur" >>"${JOBLIST}"
    done
  done
done
NPOINTS=$(wc -l <"${JOBLIST}" | tr -d ' ')
echo "devchar-cp: ${NPOINTS} corner points x 6 stacks, $(simenv_jobs) parallel jobs"

rm -f "${WORK}"/*.sum "${WORK}"/*.cur
# shellcheck disable=SC2016
xargs -P "$(simenv_jobs)" -L 1 \
  "${BASH:-/bin/bash}" -c 'exec "$0" --one "$@"' "${HERE}/run.sh" \
  <"${JOBLIST}"

EXPECTED_ROWS=$((NPOINTS * 6))
GOT=$(cat "${WORK}"/*.sum | wc -l | tr -d ' ')
if [ "${GOT}" -ne "${EXPECTED_ROWS}" ]; then
  echo "ERROR: expected ${EXPECTED_ROWS} summary rows, collected ${GOT}" >&2
  exit 1
fi

CORNER_DESC="process{typical,ff,ss,fs,sf} x temp{-40,27,125}C x vdd{2.97,3.30,3.63}V = ${NPOINTS} points, 6 stacks each"

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

while read -r corner temp vdd _rest; do
  tag="${corner}_T${temp}_V${vdd}"
  tag=$(simenv_mktag "${tag}")
  cid=$(simenv_corner_id "${corner}" "${temp}" "${vdd}")
  simenv_archive_log "${WORK}" "${tag}" "${CORNERSDIR}" "${cid}"
done <"${JOBLIST}"

OUT_SUMMARY="${CORNERSDIR}/cp_summary.csv"
OUT_CURVES="${CORNERSDIR}/cp_curves.csv"

{
  simenv_provenance "devchar-cp" "${RID}" "sim/devchar-cp/testbench/tb_cp_mirror.sp" "${CORNER_DESC}"
  cat <<'EOF'
# stacks: n_simple/n_casc/n_ws (CP sink) and p_simple/p_casc/p_ws (CP source);
#   _casc = self-biased cascode, _ws = wide-swing (low-voltage) cascode
# sizing: NMOS W=5um, PMOS W=15um, L=1um, cascode-bias diode at W/4; Iref=20uA
# vcomp_i1pct/i5pct: output voltage where |Iout| first reaches 99%/95% of isat
# vcomp_ro50: output voltage where ro falls to 50% of its mid-rail value
# headroom_*: same boundary as distance from the stack's own rail
#   (ground for n_*, Vdd for p_*)
# vth_ref/vdsat_ref: operating point of the polarity's reference mirror device
EOF
  echo "${SUMMARY_HEADER}"
  cat "${WORK}"/*.sum | sort -t, -k1,1 -k2,2 -k3,3n -k4,4n
} >"${OUT_SUMMARY}"

{
  simenv_provenance "devchar-cp (full output I-V curves)" "${RID}" \
    "sim/devchar-cp/testbench/tb_cp_mirror.sp" "${CORNER_DESC}"
  cat <<'EOF'
# Complete output characteristic of every stack at every corner, decimated from
# the 10 mV simulation grid to 50 mV. ro is a central difference on the raw
# 10 mV grid, so the knee is resolved at full simulation resolution.
EOF
  echo "${CURVES_HEADER}"
  cat "${WORK}"/*.cur | sort -t, -k1,1 -k2,2 -k3,3n -k4,4n -k5,5n
} >"${OUT_CURVES}"

# --------------------------------------------------------------------------
# Summary stats for the record's Result table, computed from the just-written
# CSV so the record text cannot drift from the data. Columns (1-indexed, after
# stripping '#' comment lines and the header row):
#   1 stack, 2 process, 3 temp_c, 4 vdd_v, 10 ro_50pct_ohm, 16 headroom_ro50_v
# --------------------------------------------------------------------------
STACK_STATS=$(grep -v '^#' "${OUT_SUMMARY}" | tail -n +2 | awk -F, '
  { key=$1
    if (!(key in romin) || $10+0<romin[key]) romin[key]=$10+0
    if (!(key in romax) || $10+0>romax[key]) romax[key]=$10+0
    if (!(key in hrmin) || $16+0<hrmin[key]) hrmin[key]=$16+0
    if (!(key in hrmax) || $16+0>hrmax[key]) hrmax[key]=$16+0
  }
  END { for (k in romin) printf "%s %.6g %.6g %.4f %.4f\n", k, romin[k], romax[k], hrmin[k], hrmax[k] }' | sort)

STACK_TABLE=$(echo "${STACK_STATS}" | awk '{printf "  | %s | %s | %s | %s | %s |\n", $1, $2, $3, $4, $5}')

RECORD="${RECORDSDIR}/${RID}.md"
{
  cat <<EOF
# Record ${RID}

- **Record ID**: ${RID}
- **Claim**: #4 -> #9 (design-input, not a spec line) -- small-signal output
  resistance and compliance boundary of six candidate charge-pump mirror
  stacks (simple / self-biased cascode / wide-swing cascode, both polarities)
  across the full PVT grid, sufficient to pick the stack and confirm
  compliance covers the VCO control range.
- **Netlist provenance**: schematic (\`sim/devchar-cp/testbench/tb_cp_mirror.sp\`)
  -> \`sim/devchar-cp/netlist-snapshots/${RID}.spice\`, SHA-256 \`${SHA}\`
- **Environment provenance**:
$(simenv_env_block)
- **Corner matrix run**: ${NPOINTS} points (5 MOS bundles x 3 temperatures x
  3 supplies), 6 candidate stacks extracted from each point's DC sweep
  - Bundles (-> \`.lib\` sections of sm141064.ngspice): \`typical\` -> typical;
    \`ff\` -> ff; \`ss\` -> ss; \`fs\` -> fs; \`sf\` -> sf
  - Temperature: -40 C, 27 C, 125 C
  - Supply: 2.97 V, 3.30 V, 3.63 V (3.3 V +/-10%)
  - **Axes not swept**: passive corner sections N/A -- no MIM/MOS caps or poly
    resistors in the DUT.
- **Methodology / criteria / limitations**:
  - Measurement topology: each stack's output is tied through its own 0 V
    ammeter to a single node \`sw\`, shared across all six stacks; one DC sweep
    of \`sw\` from 0 to Vdd in 10 mV steps traces the complete output I-V of
    every stack (through the saturation knee and into triode, not just the
    flat region). \`ro(Vout)\` is a central difference on the raw 10 mV grid;
    \`.option abstol=1e-16 reltol=1e-7 vntol=1e-9 gmin=1e-15\` is set because the
    output-resistance extraction differences currents of order 10 pA over a
    10 mV step, which the default \`abstol=1e-12\` would otherwise dominate.
  - Compliance criteria (see \`testbench/run.sh\` header comment for the exact
    definitions): \`vcomp_i1pct\`/\`vcomp_i5pct\` -- output voltage where |Iout|
    first departs >1%/>5% from its mid-rail value, walking in from mid-rail
    toward the stack's own rail (not from the extreme Vout value, which would
    be meaningless for a simple mirror that never stops climbing with Vout);
    \`vcomp_ro50\` -- output voltage where \`ro\` falls to 50% of its mid-rail
    value, the boundary that matters for a cascode, whose current stays
    accurate well past where its output resistance has already collapsed.
    \`headroom_*\` restates each boundary as distance from the stack's own rail.
  - Sizing: NMOS W=5um, PMOS W=15um, L=1um (deliberately long-channel analog
    geometry, not the digital minimum-length devices in devchar-delay);
    cascode bias diode at W/4; Iref=20uA, chosen so both polarities sit in
    moderate inversion (Vdsat ~ 0.2 V) at Iref -- the regime a charge pump
    actually uses.
  - Statistical switches: \`sw_stat_global = sw_stat_mismatch = 0\` (nominal
    device skew, no Monte Carlo). CP mismatch is a separate campaign (#15,
    \`mc-cp-mismatch\`), not this record.
- **Statistical convention**: N/A -- corner-matrix claim, not a distribution
  claim.
- **Result**: \`ro\` at the mid-rail bias point and \`ro\`-defined headroom,
  min/max across all 45 corners, per stack:

  | Stack | ro_50pct_ohm min | ro_50pct_ohm max | headroom_ro50_v min | headroom_ro50_v max |
  |---|---|---|---|---|
${STACK_TABLE}

  The cascode/wide-swing stacks are expected to show markedly higher ro than
  the simple mirrors at the cost of more headroom (higher \`headroom_ro50_v\`);
  the wide-swing variants trade some of that ro for less headroom than the
  self-biased cascode. See the full per-corner-per-stack table for the
  saturation-knee detail (vcomp_i1pct/i5pct) and the raw I-V curves.
  Full tables: \`sim/devchar-cp/corners/${RID}/cp_summary.csv\` (per-corner
  summary) and \`cp_curves.csv\` (decimated I-V curves through the knee).
- **Links**:
  - Testbench: \`sim/devchar-cp/testbench/tb_cp_mirror.sp\`
  - Netlist snapshot: \`sim/devchar-cp/netlist-snapshots/${RID}.spice\`
  - Raw logs: \`sim/devchar-cp/corners/${RID}/\`
  - Extracted metrics: \`sim/devchar-cp/corners/${RID}/cp_summary.csv\`,
    \`sim/devchar-cp/corners/${RID}/cp_curves.csv\`
- **Timestamp / author**: $(date -u +%Y-%m-%dT%H:%M:%SZ), agent-builder
- **Supersedes**: (none -- first record for this claim)
EOF
} >"${RECORD}"

echo "devchar-cp: wrote ${RECORD}"
echo "devchar-cp: wrote ${OUT_SUMMARY} and ${OUT_CURVES}"
echo "devchar-cp: wrote ${CORNERSDIR}/ (${NPOINTS} corner logs)"
