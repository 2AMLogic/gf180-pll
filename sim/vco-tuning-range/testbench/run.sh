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
EXPECTED=$((NPOINTS * ${#VCTRLS[@]}))
ROWS="${WORK}/rows.csv"
PENDING="${WORK}/pending.txt"

# A full campaign is hours of wall clock, so it is resumable. `--resume` keeps
# the rows already collected and re-runs only the (bundle, temp, vdd, band)
# points that are not complete. This is safe *because the runs are
# deterministic*: same frozen netlist, same generated deck, same simulator and
# corner sections, so a point re-run in a later pass produces byte-identical
# output to the same point run in the first pass. Rows belonging to a partially
# written point are discarded and that point is redone whole, so a run
# interrupted mid-print cannot leave a spliced result behind.
if [ "${1:-}" = "--resume" ] && [ -s "${ROWS}" ]; then
  sort -u "${ROWS}" -o "${ROWS}"
  awk -F, -v n="${#VCTRLS[@]}" '{c[$1","$2","$3","$4]++}
    END {for (k in c) if (c[k] == n) print k}' "${ROWS}" >"${WORK}/complete.txt"
  awk -F, 'NR==FNR{d[$0];next}{if (($1","$2","$3","$4) in d) print}' \
    "${WORK}/complete.txt" "${ROWS}" >"${ROWS}.keep"
  mv "${ROWS}.keep" "${ROWS}"
  awk 'NR==FNR{d[$0];next}{k=$1","$2","$3","$4; if (!(k in d)) print}' \
    "${WORK}/complete.txt" "${JOBLIST}" >"${PENDING}"
  echo "vco-tuning-range: resuming -- $(wc -l <"${ROWS}" | tr -d ' ')/${EXPECTED} rows already collected"
else
  : >"${ROWS}"
  cp "${JOBLIST}" "${PENDING}"
fi

NPEND=$(wc -l <"${PENDING}" | tr -d ' ')
echo "vco-tuning-range: ${NPEND} of ${NPOINTS} (corner, band) runs to do x ${#VCTRLS[@]} control points, $(simenv_jobs) parallel jobs"

if [ "${NPEND}" -gt 0 ]; then
  # shellcheck disable=SC2016
  xargs -P "$(simenv_jobs)" -L 1 \
    "${BASH:-/bin/bash}" -c 'exec "$0" --one "$@"' "${HERE}/run.sh" \
    <"${PENDING}" >>"${ROWS}"
fi

sort -u "${ROWS}" -o "${ROWS}"
GOT=$(wc -l <"${ROWS}" | tr -d ' ')
if [ "${GOT}" -ne "${EXPECTED}" ]; then
  echo "ERROR: expected ${EXPECTED} rows, collected ${GOT} -- re-run with --resume" >&2
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
#   Topology and sizing rationale: design/README.md.
# fosc_hz: measured at the buffered output CLK over 4 whole cycles after tsettle
# isupply_a: average current out of that instance's own VDD_VCO ammeter over
#   the measurement window (whole block: bias + ring + output buffer + decap)
# bundles: typical/ff/ss/fs/sf are MOS-only (res_typical, moscap_typical);
#   all-slow = ss+res_ss+moscap_ss ; all-fast = ff+res_ff+moscap_ff
EOF
  echo "${CSV_HEADER}"
  sort -t, -k1,1 -k2,2n -k3,3n -k4,4n -k5,5n "${ROWS}"
} >"${CSV_OUT}"

# --------------------------------------------------------------------------
# Extract Kvco / coverage checks and mint the record. Every number in the
# Result section is computed by analyze.py from the CSV just written, so the
# record cannot drift from its own evidence.
# --------------------------------------------------------------------------
RESULT="${WORK}/result.md"
python3 "${HERE}/analyze.py" "${CSV_OUT}" "${CORNERSDIR}" >"${RESULT}"

RECORD="${RECORDSDIR}/${RID}.md"
{
  cat <<EOF
# Record ${RID}

- **Record ID**: ${RID}
- **Claim**: #8 (design-input claim, and a pass/fail against two proposed spec
  lines) -- does the 5-stage current-starved ring VCO of \`design/vco.sch\`
  cover the ratified v1 output band of 10-200 MHz (DR-002 Decision 2) at every
  PVT corner, with adjacent-band overlap and no coverage hole, and with
  Kvco inside the ceiling DR-001 Decision 1's fixed loop filter assumes?
  Two of the checks below are binding on sibling issues: the **low-band floor**
  is DR-002 Decision 2's documented trigger for whether an output divider
  enters v1 scope (#11), and the **Kvco table** is the input #9/#10 size the
  charge pump and loop filter against.
  Spec-line references are placeholders pending ratification (#1):
  \`spec/pll.md#output-band\`, \`spec/pll.md#kvco\`.
- **Netlist provenance**: schematic (\`design/vco.sch\` + \`design/vco_bias.sch\`
  + \`design/vco_stage.sch\`, exported by \`design/netlist.sh\`) ->
  \`sim/vco-tuning-range/netlist-snapshots/${RID}.spice\`, SHA-256 \`${SHA}\`
- **Environment provenance**:
$(simenv_env_block)
- **Corner matrix run**: ${EXPECTED} points =
  7 corner bundles x 3 temperatures x 3 supplies x 8 band codes x 7 control
  voltages. The PVT grid is 63 points, a **superset** of the 45-point default
  grid in \`sim/README.md\`.
  - Bundles (-> \`.lib\` sections of \`sm141064.ngspice\`):
    \`typical\` -> typical, res_typical, moscap_typical;
    \`ff\` -> ff, res_typical, moscap_typical;
    \`ss\` -> ss, res_typical, moscap_typical;
    \`fs\` -> fs, res_typical, moscap_typical;
    \`sf\` -> sf, res_typical, moscap_typical;
    \`all-slow\` -> ss, res_ss, moscap_ss;
    \`all-fast\` -> ff, res_ff, moscap_ff
  - Temperature: -40 C, 27 C, 125 C
  - Supply: 2.97 V, 3.30 V, 3.63 V (3.3 V +/-10%)
  - Band code: all 8 codes of the 3-bit static band-select input (B2 B1 B0)
  - Control voltage: 0.9, 1.2, 1.5, 1.8, 2.1, 2.4, 2.7 V -- the usable Vctrl
    window DR-001 predicts (~0.9-2.4 V), extended to 2.7 V to show where the
    V->I converter's degeneration stops holding Kvco flat.
  - **Passive axes ARE swept, and deliberately so.** \`sim/README.md\` warns
    that a MOS-only sweep silently pins the passive sections at typical. This
    DUT's frequency is set by a **poly resistor** (the V->I degeneration
    resistor and the constant-gm reference resistor), so the resistor corner is
    the single most Kvco-relevant process axis. The five MOS-only bundles are
    kept for comparability with \`sim/devchar-delay\`, and the two composite
    bundles (\`all-slow\`, \`all-fast\`) add \`res_ss/res_ff\` and
    \`moscap_ss/moscap_ff\` so every reported worst case is a genuine
    worst case. MIM sections are N/A -- the decoupling capacitor is
    \`cap_nmos_03v3\` (a MOS cap), there is no MIM device in this DUT.
- **Methodology / criteria / limitations**:
  - **Measurement topology**: seven independent copies of the complete VCO
    (constant-gm bias generator + band-select mirror chain + V->I converter +
    5-stage starved ring + output buffer + on-chip decoupling) are instantiated
    in one deck, one per control voltage, at a common PVT point and band code.
    Each copy has its own supply ammeter, so f(Vctrl) and I(Vctrl) at all seven
    control points come from a single transient. The copies share only the
    ideal supply and ground nodes.
  - **Measurement criterion**: frequency is measured at the **buffered output
    \`CLK\`**, not at an internal ring node -- \`CLK\` is what the divider (#11)
    and the closed-loop bench (#12) see, and measuring there also proves the
    output buffer squares the starved ring's slow internal edges into a
    rail-to-rail clock at the bottom of the band. The period is taken over four
    whole cycles between the 1st and 5th rising half-supply crossing after
    \`tsettle\`, and \`tsettle\` is >= 4 estimated periods, so the bias
    generator's own start-up transient is excluded from every number.
  - **Kvco extraction**: local dF/dVctrl by central difference on the 0.3 V
    control grid (one-sided at the two ends), per (corner, band). Reported as
    a per-point table, not a single per-band slope, because the loop-dynamics
    design (#10) consumes the Kvco **spread**, not its average.
  - Simulator settings: \`.tran <tstep> <tstop> 0 <tmax>\` with the window
    scaled per (band, corner) from a frequency estimate -- \`tmax\` <= 1/(80
    f_max), i.e. >= 80 timesteps per cycle of the fastest instance in the deck,
    so half-supply crossings are interpolated to well under 1% of a period.
    \`uic\` is deliberately NOT used: the bias generator is solved to its DC
    operating point before t=0. \`.ic\` is applied to the ring nodes only, to
    break the metastable all-nodes-at-mid DC solution.
  - Every run is self-checking: all seven \`.meas\` frequencies must land or
    the point is retried with a 3x longer window (up to three attempts), and
    the campaign aborts unless all ${EXPECTED} rows are collected. No row in
    the CSV is an extrapolation or a default.
  - **Execution may span more than one pass.** The campaign is resumable
    (\`run.sh --resume\`), which is sound here only because the runs are
    deterministic: the same frozen netlist, generated deck, simulator build and
    corner sections produce byte-identical output for a point whichever pass
    runs it. Rows belonging to a partially written point are discarded and the
    point is redone whole, so no result is ever spliced. The record ID's
    timestamp is when the record was minted, i.e. after the last pass.
  - Statistical switches: \`sw_stat_global = sw_stat_mismatch = 0\` (nominal
    per-corner skew, no Monte Carlo mismatch). Device mismatch in the
    band-select mirror is **not** covered by this record.
  - **Limitations**:
    - **Schematic-level, no parasitics.** Ring frequency is set by the load
      capacitance of each stage, so layout parasitics will move every number
      here downward. The margins reported below are the budget that extraction
      (#18) has to stay inside, not a final result.
    - **Clean supply.** This record sweeps DC supply only; it produces a
      supply-*pushing* number but no jitter number. DR-001 names supply noise
      the top risk for this topology, and the supply-step / supply-ripple
      jitter testbench that addresses it is a separate record from
      \`testbench/run_supply.sh\`. A tuning-range record on its own does not
      discharge that acceptance criterion.
    - **Vctrl endpoints, not a servo.** Bands are characterized over a fixed
      0.9-2.7 V control window; the closed loop will not use the full window at
      every band. Band-edge numbers are therefore the *available* range.
- **Statistical convention**: N/A -- corner-matrix claim, not a distribution
  claim. Band-select mirror mismatch is a distribution claim and is out of
  scope for this record.
- **Result**:

EOF
  cat "${RESULT}"
  cat <<EOF

- **Links**:
  - Testbench: \`sim/vco-tuning-range/testbench/tb_vco_tuning.sp\`
  - Corner runner: \`sim/vco-tuning-range/testbench/run.sh\`
  - Extraction: \`sim/vco-tuning-range/testbench/analyze.py\`
  - Netlist snapshot: \`sim/vco-tuning-range/netlist-snapshots/${RID}.spice\`
  - Raw logs: \`sim/vco-tuning-range/corners/${RID}/\` (one per PVT point,
    each holding that point's eight band runs back to back)
  - Extracted metrics: \`sim/vco-tuning-range/corners/${RID}/vco_tuning.csv\`
    (raw sweep), \`kvco_by_point.csv\` (per-point Kvco),
    \`kvco_by_band.csv\` (per-band summary)
- **Timestamp / author**: $(date -u +%Y-%m-%dT%H:%M:%SZ), agent-builder (#8)
- **Supersedes**: (none -- first record for this claim)
EOF
} >"${RECORD}"

echo "vco-tuning-range: wrote ${CSV_OUT}"
echo "vco-tuning-range: wrote ${CORNERSDIR}/ (per-PVT-point logs)"
echo "vco-tuning-range: wrote ${RECORD}"
echo "vco-tuning-range: netlist sha256 ${SHA}"
echo "${RID}" >"${WORK}/last_record_id"
