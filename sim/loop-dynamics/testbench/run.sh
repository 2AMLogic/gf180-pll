#!/usr/bin/env bash
# gf180-pll :: loop-dynamics :: corner runner for the loop-filter bandwidth /
# phase-margin campaign (#10).
#
# Two testbenches feed one `analyze.py` (which does the algebra and emits the
# record's whole Result section, so no number in the record is hand-typed):
#
#   tb_loop_filter_ac.sp   small-signal Z(jw) of the REAL `design/loop_filter.sch`
#                          devices, at every (passive corner, temperature) point
#                          -- each run sweeps all six Vctrl bias points in one
#                          ngspice invocation.  This alone is exact for the whole
#                          Kvco x N x Icp-trim x f_ref cross-product; see
#                          analyze.py's module docstring for why.
#   tb_loop_ac.sp          independent cross-check: the WHOLE linearized loop
#                          (behavioural PFD/CP + real filter + behavioural VCO +
#                          divider) at a handful of real (Icp, Kvco, N) points
#                          chosen by pick_xcheck.py from #8's/#9's measured
#                          tables.
#
# The filter has NO active devices, so the swept axis is the PASSIVE corner box
# (res_*, moscap_*, mimcap_*) x temperature -- there is no MOS or supply axis
# (sim/README.md's "Default corner matrix" note: a MOS-only sweep would
# silently leave the filter's own passives at typical, which is backwards for
# this DUT; here the passive box IS the whole swept axis).  27 passive-bundle
# combinations (3 res x 3 moscap x 3 mimcap) x 3 temperatures = 81 filter runs.
#
# Usage:
#   ./run.sh                 # full campaign -> mints a records/<id>.md
#   ./run.sh --check         # nominal corner only, both benches, to stdout
#   SIM_JOBS=8 ./run.sh      # cap parallelism
#   SIM_SUPERSEDES=<id> SIM_SUPERSEDES_NOTE='<why>' SIM_METHOD_NOTE='<what>' \
#     ./run.sh               # correcting re-run (see "Supersession" below)

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP="$(cd "${HERE}/.." && pwd)"
REPO="$(cd "${EXP}/../.." && pwd)"
# shellcheck source=../../lib/simenv.sh
. "${HERE}/../../lib/simenv.sh"

DECK_Z="${HERE}/tb_loop_filter_ac.sp"
DECK_T="${HERE}/tb_loop_ac.sp"
PICK_XCHECK="${HERE}/pick_xcheck.py"
ANALYZE="${HERE}/analyze.py"
WORK="${EXP}/work"
DUT="${REPO}/design/netlist/loop_filter.spice"

# Read-only design-input evidence this campaign consumes (#8, #9) -- never
# written to, never modified.  Pinned to the record that measures the CURRENT
# design for each claim.  For cp-compliance that is `20260731-194124-afa338c`,
# which measures the post-#24 charge pump (fixed dump-node clamp replaced by
# `cp_dumpbuf`, DR-005): the earlier `20260731-122451-63e4b47` is still valid
# evidence for the design IT measured, but its per-event charge asymmetry
# (~104 fC worst case) belongs to a charge pump that no longer exists on main
# -- the current one measures ~3.7 fC, and the control-line ripple this
# campaign derives from it is ~28x smaller as a result.
KVCO_CSV="${REPO}/sim/vco-tuning-range/corners/20260731-081628-239e73b/kvco_by_point.csv"
CPDC_CSV="${REPO}/sim/cp-compliance/corners/20260731-194124-afa338c/cp_dc.csv"
CPSW_CSV="${REPO}/sim/cp-compliance/corners/20260731-194124-afa338c/cp_switch.csv"

# Passive corner sections and their short forms used in bundle names
# (r<res>-m<moscap>-x<mimcap>, e.g. rtyp-mtyp-xtyp / rss-mss-xss / rff-mff-xff
# -- "x" for the MIM axis so the three prefixes stay visually distinct).
SECTIONS=(typical ff ss)
short() { case "$1" in typical) echo typ ;; ff) echo ff ;; ss) echo ss ;; esac; }

# Vctrl bias points hardcoded inside tb_loop_filter_ac.sp itself (vb1..vb6);
# repeated here only for CSV column labeling, never passed as a param.
VCTRLS=(0.3 0.9 1.35 1.8 2.25 2.7)

FZ_HEADER="bundle,res_sec,moscap_sec,mimcap_sec,temp_c,vctrl_v,freq_hz,zmag_ohm,zph_deg"
LAC_HEADER="tag,bundle,temp_c,vctrl_v,icp_a,kvco_hz_per_v,n_div,freq_hz,tmag,tph_deg"

# --------------------------------------------------------------------------
# One filter-impedance point: run_z <res_sec> <moscap_sec> <mimcap_sec> <temp> <outcsv>
# --------------------------------------------------------------------------
run_z() {
  local rsec="$1" msec="$2" xsec="$3" temp="$4" outcsv="$5"
  local bundle="r$(short "${rsec}")-m$(short "${msec}")-x$(short "${xsec}")"
  local tag="z_${bundle}_T${temp}"
  tag=$(simenv_mktag "${tag}")

  simenv_stage_netlist "${WORK}/${tag}" "${DUT}"
  simenv_run_deck "${DECK_Z}" "${WORK}" "${tag}" \
    "res_${rsec},moscap_${msec},mimcap_${xsec}" "${temp}" >/dev/null
  local rundir="${WORK}/${tag}"
  [ -f "${rundir}/z.dat" ] || { echo "ERROR: no z.dat for tag=${tag}" >&2; return 1; }

  awk -v bundle="${bundle}" -v rsec="${rsec}" -v msec="${msec}" -v xsec="${xsec}" \
      -v temp="${temp}" -v v1="${VCTRLS[0]}" -v v2="${VCTRLS[1]}" -v v3="${VCTRLS[2]}" \
      -v v4="${VCTRLS[3]}" -v v5="${VCTRLS[4]}" -v v6="${VCTRLS[5]}" '
    {
      f = $1
      printf "%s,%s,%s,%s,%s,%s,%.8g,%.8g,%.6f\n", bundle,rsec,msec,xsec,temp,v1,f,$2,$3
      printf "%s,%s,%s,%s,%s,%s,%.8g,%.8g,%.6f\n", bundle,rsec,msec,xsec,temp,v2,f,$4,$5
      printf "%s,%s,%s,%s,%s,%s,%.8g,%.8g,%.6f\n", bundle,rsec,msec,xsec,temp,v3,f,$6,$7
      printf "%s,%s,%s,%s,%s,%s,%.8g,%.8g,%.6f\n", bundle,rsec,msec,xsec,temp,v4,f,$8,$9
      printf "%s,%s,%s,%s,%s,%s,%.8g,%.8g,%.6f\n", bundle,rsec,msec,xsec,temp,v5,f,$10,$11
      printf "%s,%s,%s,%s,%s,%s,%.8g,%.8g,%.6f\n", bundle,rsec,msec,xsec,temp,v6,f,$12,$13
    }' "${rundir}/z.dat" >"${outcsv}"
}

# --------------------------------------------------------------------------
# One loop-AC cross-check point:
#   run_t <tag> <bundle> <libs-csv> <temp> <vctrl> <icp> <kvco> <ndiv> <outcsv>
# --------------------------------------------------------------------------
run_t() {
  local tag="$1" bundle="$2" libs="$3" temp="$4" vctrl="$5" icp="$6" kvco="$7" ndiv="$8" outcsv="$9"
  local rtag="xc_${tag}"
  rtag="${rtag//./p}"; rtag="${rtag//-/m}"

  simenv_stage_netlist "${WORK}/${rtag}" "${DUT}"
  simenv_run_deck "${DECK_T}" "${WORK}" "${rtag}" "${libs}" "${temp}" \
    "icp=${icp}" "kvco=${kvco}" "ndiv=${ndiv}" "vctrl=${vctrl}" >/dev/null
  local rundir="${WORK}/${rtag}"
  [ -f "${rundir}/t.dat" ] || { echo "ERROR: no t.dat for tag=${tag}" >&2; return 1; }

  awk -v tag="${tag}" -v bundle="${bundle}" -v temp="${temp}" -v vctrl="${vctrl}" \
      -v icp="${icp}" -v kvco="${kvco}" -v ndiv="${ndiv}" '
    { printf "%s,%s,%s,%s,%s,%s,%s,%.8g,%.8g,%.6f\n", tag,bundle,temp,vctrl,icp,kvco,ndiv,$1,$2,$3 }
  ' "${rundir}/t.dat" >"${outcsv}"
}

# --------------------------------------------------------------------------
# Entry points (parallel workers)
# --------------------------------------------------------------------------
case "${1:-}" in
  --one-z) shift; run_z "$@"; exit 0 ;;
  --one-t) shift; run_t "$@"; exit 0 ;;
esac

simenv_require_tools
[ -f "${DUT}" ] || { echo "ERROR: ${DUT} missing -- run design/netlist.sh --top loop_filter" >&2; exit 1; }
mkdir -p "${WORK}"

if [ "${1:-}" = "--check" ]; then
  tmpdir=$(mktemp -d)
  trap 'rm -rf "${tmpdir}"' EXIT
  run_z typical typical typical 27 "${tmpdir}/z.csv"
  echo "${FZ_HEADER}"; cat "${tmpdir}/z.csv"
  line=$(python3 "${PICK_XCHECK}" "${KVCO_CSV}" "${CPDC_CSV}" | head -1)
  read -r tag bundle libs temp vctrl icp kvco ndiv <<<"${line}"
  run_t "${tag}" "${bundle}" "${libs}" "${temp}" "${vctrl}" "${icp}" "${kvco}" "${ndiv}" "${tmpdir}/t.csv"
  echo "${LAC_HEADER}"; cat "${tmpdir}/t.csv"
  exit 0
fi

# --------------------------------------------------------------------------
# Build the job lists.
# --------------------------------------------------------------------------
ZJOBS="${WORK}/jobs_z.txt"; : >"${ZJOBS}"
for rsec in "${SECTIONS[@]}"; do
  for msec in "${SECTIONS[@]}"; do
    for xsec in "${SECTIONS[@]}"; do
      for temp in "${SIMENV_TEMPS[@]}"; do
        bundle="r$(short "${rsec}")-m$(short "${msec}")-x$(short "${xsec}")"
        tag="z_${bundle}_T${temp}"; tag=$(simenv_mktag "${tag}")
        echo "${rsec} ${msec} ${xsec} ${temp} ${WORK}/${tag}.csv" >>"${ZJOBS}"
      done
    done
  done
done
NZ=$(wc -l <"${ZJOBS}" | tr -d ' ')

TJOBS="${WORK}/jobs_t.txt"; : >"${TJOBS}"
python3 "${PICK_XCHECK}" "${KVCO_CSV}" "${CPDC_CSV}" | while read -r tag bundle libs temp vctrl icp kvco ndiv; do
  rtag="xc_${tag}"; rtag="${rtag//./p}"; rtag="${rtag//-/m}"
  echo "${tag} ${bundle} ${libs} ${temp} ${vctrl} ${icp} ${kvco} ${ndiv} ${WORK}/${rtag}.csv" >>"${TJOBS}"
done
NT=$(wc -l <"${TJOBS}" | tr -d ' ')

echo "loop-dynamics: ${NZ} filter-impedance corner points (x6 Vctrl each) + ${NT} independent loop-AC cross-check points, $(simenv_jobs) parallel jobs"

rm -f "${WORK}"/z_*.csv "${WORK}"/xc_*.csv

# shellcheck disable=SC2016
xargs -P "$(simenv_jobs)" -L 1 \
  "${BASH:-/bin/bash}" -c 'exec "$0" --one-z "$@"' "${HERE}/run.sh" <"${ZJOBS}"
# shellcheck disable=SC2016
xargs -P "$(simenv_jobs)" -L 1 \
  "${BASH:-/bin/bash}" -c 'exec "$0" --one-t "$@"' "${HERE}/run.sh" <"${TJOBS}"

GOTZ=$(find "${WORK}" -maxdepth 1 -name 'z_*.csv' | wc -l | tr -d ' ')
GOTT=$(find "${WORK}" -maxdepth 1 -name 'xc_*.csv' | wc -l | tr -d ' ')
[ "${GOTZ}" -eq "${NZ}" ] || { echo "ERROR: expected ${NZ} filter-Z csvs, found ${GOTZ}" >&2; exit 1; }
[ "${GOTT}" -eq "${NT}" ] || { echo "ERROR: expected ${NT} loop-AC csvs, found ${GOTT}" >&2; exit 1; }

FZ_RAW="${WORK}/filter_z_raw.csv"
{ echo "${FZ_HEADER}"; cat "${WORK}"/z_*.csv; } >"${FZ_RAW}"
LAC_RAW="${WORK}/loop_ac_raw.csv"
{ echo "${LAC_HEADER}"; cat "${WORK}"/xc_*.csv; } >"${LAC_RAW}"

NZROWS=$(($(wc -l <"${FZ_RAW}" | tr -d ' ') - 1))
NTROWS=$(($(wc -l <"${LAC_RAW}" | tr -d ' ') - 1))
echo "loop-dynamics: collected ${NZROWS} filter-Z rows, ${NTROWS} loop-AC cross-check rows"

# --------------------------------------------------------------------------
# Supersession (sim/README.md :: Status / supersession language).
#
# A record is frozen at mint time and can never be edited afterwards, so
# anything that has to be TRUE OF THIS RUN rather than of the campaign has to
# be settable from outside (same convention as sim/cp-compliance/testbench):
#
#   SIM_SUPERSEDES=<record-id>        the record this run replaces
#   SIM_SUPERSEDES_NOTE=<one line>    why
#   SIM_METHOD_NOTE=<text>            one extra Methodology bullet, e.g. which
#                                     design revision of a CONSUMED input this
#                                     run reads and what it is comparable to
#   SIM_AUTHOR=<who>                  attribution, when a later issue re-runs
#                                     this campaign
#
# Unset, all four fall back to the wording this campaign was minted with, so
# an unqualified re-run emits exactly what it emitted before.
# --------------------------------------------------------------------------
# --------------------------------------------------------------------------
# Mint the evidence record (sim/README.md convention).
# --------------------------------------------------------------------------
RID=$(simenv_record_id)
SNAPDIR="${EXP}/netlist-snapshots"
CORNERSDIR="${EXP}/corners/${RID}"
RECORDSDIR="${EXP}/records"
mkdir -p "${SNAPDIR}" "${CORNERSDIR}" "${RECORDSDIR}"

cp "${DUT}" "${SNAPDIR}/${RID}.spice"
SHA=$(simenv_sha256 "${SNAPDIR}/${RID}.spice")

echo "loop-dynamics: archiving ${NZ} filter + ${NT} cross-check corner logs ..."
while read -r rsec msec xsec temp _rest; do
  bundle="r$(short "${rsec}")-m$(short "${msec}")-x$(short "${xsec}")"
  tag="z_${bundle}_T${temp}"; tag=$(simenv_mktag "${tag}")
  cid="z_${bundle}_${temp}c"
  simenv_archive_log "${WORK}" "${tag}" "${CORNERSDIR}" "${cid}"
done <"${ZJOBS}"
while read -r tag _rest; do
  rtag="xc_${tag}"; rtag="${rtag//./p}"; rtag="${rtag//-/m}"
  simenv_archive_log "${WORK}" "${rtag}" "${CORNERSDIR}" "xcheck_${tag}"
done <"${TJOBS}"

# --------------------------------------------------------------------------
# Run the analysis. analyze.py writes filter_rc.csv, loop_margins.csv,
# loop_margins_by_filter_corner.csv, kappa_by_target.csv, ripple_tradeoff.csv,
# loop_ac_crosscheck.csv and a decimated filter_z.csv into CORNERSDIR, and
# prints the record's whole Markdown "Result" section on stdout.
# --------------------------------------------------------------------------
echo "loop-dynamics: running analyze.py ..."
RESULT_MD="${WORK}/result.md"
python3 "${ANALYZE}" "${FZ_RAW}" "${LAC_RAW}" "${KVCO_CSV}" "${CPDC_CSV}" "${CPSW_CSV}" \
  "${CORNERSDIR}" >"${RESULT_MD}"

RECORD="${RECORDSDIR}/${RID}.md"
{
  cat <<EOF
# Record ${RID}

- **Record ID**: ${RID}
- **Claim**: #4/#8/#9 -> #10 (design-input claim, not a spec line) -- DR-001
  Decision 1's fixed, non-programmable second-order loop filter (series R +
  shunt C1 + shunt C2) is sized from #4's real \`sim/devchar-passives\` device
  data (\`ppolyf_u\` for R, the body-tied \`cap_nmos_03v3_b\` for C1, MIM for
  C2 -- see \`design/loop_filter.sch\`).  Does that realized filter meet an
  explicit phase-margin criterion and the \`f_c < f_ref/10\` sampled-loop
  ceiling at every point in the PVT x Kvco-spread x N=4-64 x Icp-trim
  cross-product DR-001 asks this issue to check, using #8's actual extracted
  Kvco(Vctrl) table and #9's actual Icp/trim data -- not the DR-001 hand-calc
  placeholders?  Also: C1's real area against the 0.15 mm^2 budget, and the
  ripple-vs-lock-time tradeoff DR-001's hand calc predicted but did not
  measure.
- **Netlist provenance**: schematic (\`design/loop_filter.sch\`, exported by
  \`design/netlist.sh --top loop_filter\`) ->
  \`sim/loop-dynamics/netlist-snapshots/${RID}.spice\`, SHA-256 \`${SHA}\`.
  The two testbench decks (\`tb_loop_filter_ac.sp\`, \`tb_loop_ac.sp\`) contain
  stimulus and measurement only; \`tb_loop_ac.sp\` additionally carries
  behavioural (non-DUT) models of the PFD/CP, VCO and divider, described in
  its own header comment.
- **Environment provenance**:
$(simenv_env_block "$(simenv_xschem_version) (batch netlist export of
    \`design/loop_filter.sch\` via \`design/netlist.sh\`; the DUT netlist is a
    schematic export, not a hand-written deck)")
- **Corner matrix run**: ${NZ} filter-impedance points (27 passive-corner
  bundles x 3 temperatures), each swept over 6 Vctrl bias points in one
  ngspice AC analysis (100 Hz - 100 MHz, 40 points/decade) = ${NZROWS} raw
  (bundle, temp, Vctrl, freq) rows; plus ${NT} independent loop-AC cross-check
  points (\`tb_loop_ac.sp\`, one per (f_ref, N, Icp-trim-code) design point x 3
  filter corners) = ${NTROWS} rows.  The loop-gain constant
  \`A = Icp*Kvco/N\` is then swept on a ${A_GRID:-25}-point log grid between
  its measured extremes for EVERY (f_ref, N, Icp-trim-code) legal combination
  against every in-window filter curve -- see "Methodology" below for why one
  measured Z(jw) curve per filter corner covers that whole combination exactly
  rather than approximately.
  - **Filter-impedance axis (this DUT has no active devices, so NO MOS or
    supply corner applies)**: the three INDEPENDENT passive corner sections
    of \`sm141064.ngspice\`, swept together as all 27 combinations:
    \`res_{typical,ff,ss}\` (the series R, \`ppolyf_u\`) x
    \`moscap_{typical,ff,ss}\` (C1, \`cap_nmos_03v3_b\`) x
    \`mimcap_{typical,ff,ss}\` (C2, \`cap_mim_2f0_m2m3_noshield\`).  Bundle
    names are \`r<res>-m<moscap>-x<mimcap>\` with \`typ/ff/ss\` short forms,
    e.g. \`rtyp-mtyp-xtyp\` (all-typical), \`rss-mss-xss\` (the slow corner:
    largest R, largest C1, so the smallest \`f_c\`), \`rff-mff-xff\` (the fast
    corner: smallest R, smallest C1, so the largest \`f_c\`).
  - Temperature: -40 C, 27 C, 125 C.
  - **Vctrl bias points**: 0.9, 1.35, 1.8, 2.25, 2.7 V (the DR-003 Decision 5
    usable window) plus 0.3 V (BELOW the window, characterized only for the
    C1 C-V collapse check during cold-start acquisition -- excluded from the
    stability cross-product itself).
  - **Axes not swept**: MOS process bundles (\`tt/ff/ss/fs/sf\`) N/A -- the
    filter contains no active device; supply (\`vdd\`) N/A for the same reason
    -- neither the impedance testbench nor the filter itself has a supply
    node. The loop-AC cross-check's behavioural PFD/CP and VCO blocks are
    ideal (Icp/Kvco/N are injected as measured numbers from #8/#9, not
    resimulated), so they carry no PVT dependence of their own to sweep.
  - Icp-trim axis: all 4 of #9's 2-bit trim codes (1-4 unit legs), each
    evaluated against \`icp[code].lo\`/\`.hi\` -- the min/max Icp that code
    delivers across #9's own 45 PVT corners (\`sim/cp-compliance\`) -- so the
    charge-pump's OWN corner spread is folded into the \`A\` axis rather than
    re-simulated here.
  - Kvco-spread axis: for every legal (f_ref, N) pair, the min/max Kvco
    #8 measured (\`sim/vco-tuning-range\`) across ALL its own 63 PVT corners,
    under the DR-003 Decision 4 band-selection rule (lowest band that reaches
    f_out) -- so the VCO's own corner spread is likewise folded into \`A\`
    rather than re-simulated here.
  - Reference frequency axis: 1, 2, 4, 8, 16, 25 MHz (log-spaced across the
    ratified 1-25 MHz range, both endpoints included).
  - Divider axis: N in {4, 6, 8, 12, 16, 24, 32, 48, 64}, restricted per f_ref
    to the pairs whose \`f_ref*N\` lands inside the ratified 10-200 MHz v1
    output band (DR-002 Decision 2) -- an (f_ref, N) pair outside that band is
    not a configuration the part can actually be put in, so it is excluded
    rather than reported as a failure.
- **Methodology / criteria / limitations**:
  - **Exact reduction, not an approximation.** For the type-II charge-pump
    loop of DR-001 Decision 1, \`T(s) = (Icp/2pi)*Z(s)*(2pi*Kvco/s)/N =
    A*Z(s)/s\` with \`A = Icp*Kvco/N\`, so Icp, Kvco and N enter ONLY through
    the scalar A. One measured filter impedance curve per (passive corner,
    temperature, Vctrl) point therefore covers the ENTIRE Kvco x N x Icp-trim
    x f_ref cross-product for that filter corner exactly, rather than by
    interpolation or a monotonicity argument -- see \`analyze.py\`'s module
    docstring for the derivation. The A axis is still swept on a dense
    (${A_GRID:-25}-point) log grid between its measured extremes, not just
    evaluated at the extremes, so no unimodality assumption is relied on
    either.
  - **Independent cross-check.** \`tb_loop_ac.sp\` puts the real filter inside
    a phase-domain behavioural model of the WHOLE loop (charge pump as an
    Icp/2pi A/rad gain, VCO as an ideal phase integrator, divider as 1/N) and
    lets ngspice compute \`T(jw)\` directly at real (Icp, Kvco, N) points
    \`pick_xcheck.py\` selects from #8's/#9's measured tables -- one point per
    reference-frequency decade x the three extreme filter corners. Section 8
    of the Result reports the agreement between this independent simulation
    and the impedance-plus-algebra result.
  - **Criteria applied** (stated up front, not left implicit): phase margin
    >= 45 deg everywhere in the operating space (this record's own adopted
    criterion -- DR-001 states none); \`f_c < f_ref/10\`, the sampled-loop
    stability ceiling DR-001 Decision 1 names explicitly; small-signal 1 %
    settling < 100 us (draft lock-time target, 20 us stretch); C1 area
    reported against the draft 0.15 mm^2 block budget.
  - **R/C1/C2 are not drawn values here, they are MEASURED** from each Z(jw)
    curve's own asymptotes and phase peak (a 3-element fit), so process/temp
    variation on the real devices is what actually drives the swept filter
    corner, not a separate hand-scaled R/C.
  - **Band-selection rule is load-bearing (DR-003 Decision 4).** Kvco is
    taken under the rule that a correctly configured part selects the LOWEST
    band that reaches the target f_out; #8's record separately reports an
    adversarial-band-choice Kvco that exceeds DR-001's ~150 MHz/V ceiling, and
    that adversarial case is NOT part of this record's cross-product (it is
    not a legal configuration).
  - **Lock-time is a small-signal estimate**, from the fitted 3-element
    model's dominant closed-loop pole -- cycle slipping and the VCO's
    large-signal nonlinearity during cold-start acquisition are #12's number,
    not this record's; stated as a limitation, not silently extrapolated.
  - **Schematic-level, no parasitics.** Routing/coupling parasitics on the
    filter's own R/C network are not in this record; #18 (extraction) is
    where those enter.
  - Statistical switches: \`sw_stat_global = sw_stat_mismatch = 0\` (nominal
    per-corner skew, no Monte Carlo) -- inherited from the underlying #4/#8/#9
    records this campaign consumes.$(simenv_method_note)
- **Statistical convention**: N/A -- corner-matrix claim, not a distribution
  claim.
- **Result**:
$(cat "${RESULT_MD}")
- **Links**:
  - Testbenches: \`sim/loop-dynamics/testbench/tb_loop_filter_ac.sp\`,
    \`sim/loop-dynamics/testbench/tb_loop_ac.sp\`,
    \`sim/loop-dynamics/testbench/pick_xcheck.py\`,
    \`sim/loop-dynamics/testbench/analyze.py\`,
    \`sim/loop-dynamics/testbench/run.sh\`
  - Design: \`design/loop_filter.sch\`, \`design/loop_filter.sym\`,
    \`design/netlist/loop_filter.spice\`
  - Consumed design-input evidence (read-only): \`${KVCO_CSV#"${REPO}"/}\`,
    \`${CPDC_CSV#"${REPO}"/}\`, \`${CPSW_CSV#"${REPO}"/}\`
  - Netlist snapshot: \`sim/loop-dynamics/netlist-snapshots/${RID}.spice\`
  - Raw logs: \`sim/loop-dynamics/corners/${RID}/\` (${NZ} filter-impedance +
    ${NT} loop-AC cross-check logs)
  - Extracted metrics: \`sim/loop-dynamics/corners/${RID}/filter_rc.csv\`
    (measured R/C1/C2 per filter corner), \`loop_margins.csv\` (the full
    (f_ref, N, trim-code) cross-product verdict), \`loop_margins_by_filter_corner.csv\`,
    \`kappa_by_target.csv\` (Kvco/f_out per f_ref/N under the three
    band-selection rules), \`ripple_tradeoff.csv\`, \`loop_ac_crosscheck.csv\`,
    \`filter_z.csv\` (decimated measured impedance curves)
- **Timestamp / author**: $(date -u +%Y-%m-%dT%H:%M:%SZ), ${SIM_AUTHOR:-agent-builder (issue #10)}
$(simenv_supersedes_field "${SIM_SUPERSEDES:-}")
EOF
} >"${RECORD}"

echo "loop-dynamics: wrote ${RECORD}"
echo "loop-dynamics: wrote ${CORNERSDIR}/ (${NZ} + ${NT} corner logs, extracted-metric CSVs)"
echo "loop-dynamics: wrote ${SNAPDIR}/${RID}.spice"
