#!/usr/bin/env bash
# gf180-pll :: pfd-deadzone :: corner + phase-offset runner
#
# Sweeps tb_pfd_deadzone.sp over the full repo PVT grid AND a phase-offset
# (dphi) sweep through zero, to verify the dead-zone-elimination requirement
# DR-001 Decision 1 puts on the PFD.
#
# The acceptance criterion is stated in the CHARGE domain, not the logic
# domain: at every one of the 45 default PVT corners, the net charge the pump
# delivers per reference cycle must stay proportional to the phase error
# through dphi = 0 -- no flat region.  A PFD whose UP/DN pulses are non-zero
# but too narrow to turn the charge-pump switches fully on would pass a
# pulse-width check and still have a dead zone; this runner checks the small
# signal gain near zero against the gain measured further out, per corner:
#
#   kd_near = [q(+200ps) - q(-200ps)] / 400ps   (the gain AT the lock point)
#   kd_wide = [q(+1ns)   - q(-1ns)  ] / 2ns      (the gain well away from it)
#   ratio   = kd_near / kd_wide                  (1.0 = perfectly linear; a
#                                                 dead zone drives it to 0)
#
# Usage:
#   ./run.sh                 # full grid -> mints a records/<id>.md (see below)
#   ./run.sh --check         # nominal corner only, full dphi sweep, to stdout
#   SIM_JOBS=4 ./run.sh      # cap parallelism
#
# A full run mints one record ID and writes, under sim/pfd-deadzone/ (per
# sim/README.md, the repo's append-only evidence-record convention):
#   netlist-snapshots/<id>.spice   frozen xschem export of the DUT hierarchy
#   corners/<id>/<corner-id>.log   raw ngspice output, one per (PVT, dphi) point
#   corners/<id>/pfd_deadzone.csv  extracted qnet/width_up/width_dn per point
#   records/<id>.md                summary record (the citable evidence object)

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP="$(cd "${HERE}/.." && pwd)"
REPO="$(cd "${EXP}/../.." && pwd)"
# shellcheck source=../../lib/simenv.sh
. "${HERE}/../../lib/simenv.sh"

DECK="${HERE}/tb_pfd_deadzone.sp"
WORK="${EXP}/work"
NETLIST="${WORK}/dut.spice"

# dphi sweep points (seconds, SPICE suffix form).  +/-200 ps is well inside the
# PFD's own reset-delay window (the minimum UP/DN pulse is 1.1-1.9 ns across
# corners), which is the region a dead zone would live in; +/-1 ns is outside
# it.  These five points are exactly what the verdict below needs -- the
# near-zero pair, the wide pair, and zero itself -- and each one costs a full
# transient at every one of the 45 corners, so the list is kept to what is used.
#
# Why the near pair is +/-200 ps and not tighter: the measured quantity is an
# integrated charge of order 10 fC, and the trapezoidal integration noise on it
# is a few tenths of a femtocoulomb.  At +/-50 ps the signal being differenced
# is only about 0.1-0.5 fC -- comparable to that floor -- and the ratio below
# becomes noise (an earlier run at +/-50 ps produced ratios scattered to
# negative values at corners whose pulse-width data was perfectly clean).
# +/-200 ps keeps the differenced signal several times the floor while staying
# well inside the reset window.
DPHI_POINTS=(-1n -200p 0 200p 1n)

SUMMARY_HEADER="process,temp_c,vdd_v,dphi_s,qnet_c,width_up_s,width_dn_s"

# --------------------------------------------------------------------------
# Single (corner, dphi) point.
#   run_one <corner> <temp> <vdd> <dphi> <summary-out>
# --------------------------------------------------------------------------
run_one() {
  local corner="$1" temp="$2" vdd="$3" dphi="$4" sfile="$5"
  local tag="${corner}_T${temp}_V${vdd}_D${dphi}"
  tag="${tag//./p}"
  tag="${tag//-/m}"

  # The deck `.include`s "dut.spice" relative to its run directory: `.include`
  # takes no parameter substitution, so the xschem export is PLACED next to the
  # generated deck rather than pointed at.
  mkdir -p "${WORK}/${tag}"
  cp "${NETLIST}" "${WORK}/${tag}/dut.spice"

  simenv_run_deck "${DECK}" "${WORK}" "${tag}" "${corner}" "${temp}" \
    "vsup=${vdd}" "dphi=${dphi}" >/dev/null
  local rundir="${WORK}/${tag}"

  local line qnet width_up width_dn
  line=$(grep "^PFD_RESULT " "${rundir}/ngspice.log" | tail -1)
  if [ -z "${line}" ]; then
    echo "ERROR: missing PFD_RESULT for tag=${tag}" >&2
    return 1
  fi
  qnet=$(echo "${line}" | sed -n 's/.*qnet=\([^ ]*\).*/\1/p')
  width_up=$(echo "${line}" | sed -n 's/.*width_up=\([^ ]*\).*/\1/p')
  width_dn=$(echo "${line}" | sed -n 's/.*width_dn=\([^ ]*\).*/\1/p')

  printf '%s,%s,%s,%s,%s,%s,%s\n' "${corner}" "${temp}" "${vdd}" "${dphi}" \
    "${qnet}" "${width_up}" "${width_dn}" >>"${sfile}"
}

# --------------------------------------------------------------------------
# Entry points
# --------------------------------------------------------------------------
if [ "${1:-}" = "--one" ]; then
  shift
  run_one "$@"
  exit 0
fi

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

# Export the design hierarchy from xschem ONCE per run: every corner point
# simulates the same netlist, and that netlist is what the record freezes.
echo "pfd-deadzone: exporting design/ via xschem ..."
"${REPO}/design/netlist.sh" --top pfd_cp "${WORK}" >/dev/null
[ -f "${NETLIST}" ] || { echo "ERROR: ${NETLIST} not produced" >&2; exit 1; }

if [ "${1:-}" = "--check" ]; then
  tmpdir=$(mktemp -d)
  trap 'rm -rf "${tmpdir}"' EXIT
  for dphi in "${DPHI_POINTS[@]}"; do
    run_one typical 27 3.30 "${dphi}" "${tmpdir}/s.csv"
  done
  echo "${SUMMARY_HEADER}"
  cat "${tmpdir}/s.csv"
  exit 0
fi

JOBLIST="${WORK}/jobs.txt"
: >"${JOBLIST}"
for corner in "${SIMENV_MOS_CORNERS[@]}"; do
  for temp in "${SIMENV_TEMPS[@]}"; do
    for vdd in "${SIMENV_VDDS[@]}"; do
      for dphi in "${DPHI_POINTS[@]}"; do
        tag="${corner}_T${temp}_V${vdd}_D${dphi}"
        tag="${tag//./p}"; tag="${tag//-/m}"
        echo "${corner} ${temp} ${vdd} ${dphi} ${WORK}/${tag}.sum" >>"${JOBLIST}"
      done
    done
  done
done
NPOINTS=$(wc -l <"${JOBLIST}" | tr -d ' ')
NCORNERS=$(( NPOINTS / ${#DPHI_POINTS[@]} ))
echo "pfd-deadzone: ${NCORNERS} PVT corners x ${#DPHI_POINTS[@]} dphi points = ${NPOINTS} runs, $(simenv_jobs) parallel jobs"

rm -f "${WORK}"/*.sum
# shellcheck disable=SC2016
xargs -P "$(simenv_jobs)" -L 1 \
  "${BASH:-/bin/bash}" -c 'exec "$0" --one "$@"' "${HERE}/run.sh" \
  <"${JOBLIST}"

GOT=$(cat "${WORK}"/*.sum | wc -l | tr -d ' ')
if [ "${GOT}" -ne "${NPOINTS}" ]; then
  echo "ERROR: expected ${NPOINTS} summary rows, collected ${GOT}" >&2
  exit 1
fi

DPHI_LIST=$(IFS=,; echo "${DPHI_POINTS[*]}")
CORNER_DESC="process{typical,ff,ss,fs,sf} x temp{-40,27,125}C x vdd{2.97,3.30,3.63}V = ${NCORNERS} PVT points, each swept over dphi{${DPHI_LIST}} = ${NPOINTS} runs"

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

while read -r corner temp vdd dphi _rest; do
  tag="${corner}_T${temp}_V${vdd}_D${dphi}"
  tag="${tag//./p}"; tag="${tag//-/m}"
  cid="$(simenv_corner_id "${corner}" "${temp}" "${vdd}")_dphi${dphi}"
  simenv_archive_log "${WORK}" "${tag}" "${CORNERSDIR}" "${cid}"
done <"${JOBLIST}"

OUT_SUMMARY="${CORNERSDIR}/pfd_deadzone.csv"
{
  simenv_provenance "pfd-deadzone" "${RID}" "design/pfd_cp.sch (xschem export)" "${CORNER_DESC}"
  cat <<'EOF'
# ref period 40 ns (25 MHz, the top of DR-002's ratified 1-25 MHz v1 range)
# vctrl held at 1.65 V; Icp trim code b1b0=10 (3 unit legs)
# dphi: FB-relative-to-REF phase offset (s)
# qnet: net charge delivered to the control node per reference cycle (C),
#   positive = pump sourcing.  This is the dead-zone-critical quantity.
# width_up/width_dn: UP/DN pulse width (s) at the per-corner mid-supply
#   crossing, third reference cycle.  Their MINIMUM is the PFD reset delay
#   that #11's retiming pulse must be at least as wide as.
EOF
  echo "${SUMMARY_HEADER}"
  cat "${WORK}"/*.sum | sort -t, -k1,1 -k2,2n -k3,3n -k4,4
} >"${OUT_SUMMARY}"

# --------------------------------------------------------------------------
# Per-corner dead-zone verdict, computed from the just-written CSV so the
# record text cannot drift from the data.
# --------------------------------------------------------------------------
STATS=$(grep -v '^#' "${OUT_SUMMARY}" | tail -n +2 | awk -F, '
  function key(r) { return $1 "/" $2 "C/" $3 "V" }
  {
    k = $1 "/" $2 "C/" $3 "V"
    q[k "," $4] = $5 + 0
    wu[k "," $4] = $6 + 0
    wd[k "," $4] = $7 + 0
    if (!(k in seen)) { seen[k] = 1; order[++n] = k }
  }
  END {
    worst_ratio = 1e9; nfail = 0
    for (i = 1; i <= n; i++) {
      k = order[i]
      kd_near = (q[k ",200p"] - q[k ",-200p"]) / 400e-12
      kd_wide = (q[k ",1n"]  - q[k ",-1n"])  / 2e-9
      ratio = (kd_wide != 0) ? kd_near / kd_wide : 0
      wmin = wu[k ",0"] < wd[k ",0"] ? wu[k ",0"] : wd[k ",0"]
      qoff = q[k ",0"]
      toff = (kd_wide != 0) ? -qoff / kd_wide : 0
      printf "ROW %s %.6g %.6g %.4f %.6g %.6g %.6g\n", k, kd_near, kd_wide, ratio, wmin, qoff, toff
      if (ratio < worst_ratio) { worst_ratio = ratio; worst_k = k }
      if (ratio < 0.5 || wu[k ",0"] <= 0 || wd[k ",0"] <= 0) {
        nfail++
        fails = fails "\n  " k ": ratio=" ratio " width_up=" wu[k ",0"] " width_dn=" wd[k ",0"]
      }
      if (kd_wide < kdmin || kdmin == 0) kdmin = kd_wide
      if (kd_wide > kdmax) kdmax = kd_wide
      if (wmin < wminall || wminall == 0) wminall = wmin
      if (wmin > wmaxall) wmaxall = wmin
      aq = qoff < 0 ? -qoff : qoff
      if (aq > qoffmax) { qoffmax = aq; qoffmax_k = k }
      at = toff < 0 ? -toff : toff
      if (at > toffmax) { toffmax = at; toffmax_k = k }
    }
    printf "SUMMARY n=%d worst_ratio=%.4f worst_corner=%s nfail=%d kd_min=%.6g kd_max=%.6g wmin_min=%.6g wmin_max=%.6g qoff_absmax=%.6g qoff_absmax_corner=%s toff_absmax=%.6g toff_absmax_corner=%s\n", n, worst_ratio, worst_k, nfail, kdmin, kdmax, wminall, wmaxall, qoffmax, qoffmax_k, toffmax, toffmax_k
    if (nfail > 0) printf "FAILURES:%s\n", fails; else printf "FAILURES: none\n"
  }')

echo "${STATS}" | grep '^SUMMARY'
echo "${STATS}" | grep '^FAILURES'

# Pull one key=value out of the SUMMARY line.  The leading-space anchor is
# load-bearing: an unanchored `grep -o "n=..."` also matches the "n=" inside
# `kd_min=` and `wmin_min=`, which silently turns a scalar into three lines of
# record text.
get() { echo "${STATS}" | grep '^SUMMARY' | grep -oE "(^| )$1=[^ ]*" | tr -d ' ' | cut -d= -f2; }
NCHK=$(get n); WORST_RATIO=$(get worst_ratio); WORST_CORNER=$(get worst_corner)
NFAIL=$(get nfail); KDMIN=$(get kd_min); KDMAX=$(get kd_max)
WMIN=$(get wmin_min); WMAX=$(get wmin_max)
QOFF=$(get qoff_absmax); QOFF_C=$(get qoff_absmax_corner)
TOFF=$(get toff_absmax); TOFF_C=$(get toff_absmax_corner)
VERDICT=$([ "${NFAIL}" -eq 0 ] && echo "PASS" || echo "FAIL")

# Per-corner table for the record.
CORNER_TABLE=$(echo "${STATS}" | awk '$1 == "ROW" {printf "  | %s | %.3g | %.3g | %.3f | %.4g | %.3g | %.4g |\n", $2, $3, $4, $5, $6, $7, $8}')

# The extracted per-corner metrics also land beside the logs as a CSV.
{
  simenv_provenance "pfd-deadzone (per-corner dead-zone verdict)" "${RID}" \
    "design/pfd_cp.sch (xschem export)" "${CORNER_DESC}"
  cat <<'EOF'
# kd_near: charge-pump gain at the lock point, [q(+200ps)-q(-200ps)]/400ps (A)
# kd_wide: same, measured out at +/-1 ns (A)
# ratio:   kd_near / kd_wide -- 1.0 is perfectly linear through zero, a dead
#          zone drives it toward 0.  Acceptance: > 0.5 at every corner.
# wmin_zero: smaller of the two UP/DN pulse widths at dphi=0 (s) = PFD reset delay
# q_zero:  net charge per reference cycle at dphi=0 (C) -- the residual
#          up/down asymmetry the loop must null out
# t_offset: static phase offset that nulls it, -q_zero/kd_wide (s)
corner,kd_near_a,kd_wide_a,ratio,wmin_zero_s,q_zero_c,t_offset_s
EOF
  echo "${STATS}" | awk '$1 == "ROW" {printf "%s,%.6g,%.6g,%.4f,%.6g,%.6g,%.6g\n", $2, $3, $4, $5, $6, $7, $8}'
} >"${CORNERSDIR}/pfd_deadzone_verdict.csv"

RECORD="${RECORDSDIR}/${RID}.md"
{
  cat <<EOF
# Record ${RID}

- **Record ID**: ${RID}
- **Claim**: #9 (design-input claim, not a spec line) -- does the tri-state PFD
  of DR-001 Decision 1, driving its own charge pump, deliver charge
  proportionally through ZERO phase error at every PVT corner (i.e. is it
  dead-zone free), and what is the residual charge offset at zero phase error
  that the loop must null as static phase error?  DR-001 Decision 1's fixed
  passive filter assumes a linear phase detector at the lock point; a dead zone
  puts a piecewise-nonlinear region exactly there.
- **Netlist provenance**: schematic (\`design/pfd_cp.sch\`, with
  \`design/pfd.sch\`, \`design/cp.sch\` and the cells below them) exported to
  SPICE by \`design/netlist.sh\` (xschem batch netlister) ->
  \`sim/pfd-deadzone/netlist-snapshots/${RID}.spice\`, SHA-256 \`${SHA}\`.
  The testbench deck contains stimulus and measurement only: there is no
  hand-transcribed copy of the design in \`sim/\`.
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
    \`moscap_*\`) N/A -- the DUT contains no resistors or capacitors, only
    \`nfet_03v3\`/\`pfet_03v3\` (DR-002 Decision 3).  The loop filter, which is
    where the passive skews matter, is #10's deliverable and is not in this
    DUT: the control node here is held by an ideal source.
  - **Also not swept**: the 2-bit Icp trim is held at code b1b0 = 10 (3 unit
    legs, the nominal setting).  Trim range is characterized across corners by
    the \`cp-compliance\` campaign; the dead-zone property is a function of the
    PFD's reset delay and the switch turn-on, which the unit-element trim
    construction leaves unchanged (every code runs the same per-leg current).
- **Methodology / criteria / limitations**:
  - **Criterion (this is the load-bearing choice)**: dead-zone freedom is
    judged in the CHARGE domain, not the logic domain.  A PFD whose UP/DN
    outputs technically toggle but whose pulses are too narrow to turn the
    charge-pump switches fully on still presents the loop with a flat region
    around zero.  So the DUT is \`pfd_cp\` -- the PFD loaded by its real charge
    pump -- and the measured quantity is \`qnet\`, the net charge delivered to
    the control node per reference cycle.  Per corner:
    \`kd_near = [q(+200ps) - q(-200ps)] / 400ps\` is the detector gain AT the
    lock point and \`kd_wide = [q(+1ns) - q(-1ns)] / 2ns\` the gain well
    outside it; the verdict is \`ratio = kd_near / kd_wide > 0.5\` at every
    corner, together with a non-zero UP and DN pulse at dphi = 0.  A true dead
    zone drives the ratio to 0.  The near pair is +/-200 ps rather than
    tighter because the differenced charge at +/-50 ps is comparable to the
    trapezoidal integration noise floor of a few tenths of a femtocoulomb;
    +/-200 ps is still well inside the 1.1-1.9 ns minimum UP/DN pulse, so it
    probes the same region with a signal several times the floor.
  - Reference 25 MHz (40 ns period) -- the TOP of DR-002 Decision 1's ratified
    1-25 MHz v1 range, chosen deliberately: the PFD's reset-and-recover window
    is the largest fraction of the reference period there, so it is the
    demanding end for this claim.
  - Transient: 3 reference cycles, 20 ps maximum timestep, \`reltol\` 1e-4 /
    \`abstol\` 1e-14; charge integrated over the last two cycles and halved.
    The first cycle is discarded as startup.  REF and FB edges have 200 ps
    rise/fall (a buffered clock edge, not an ideal step, which would flatter
    every delay in the set path).
  - Control node held at 1.65 V by an ideal source -- mid of DR-001 Decision
    2's ~0.9-2.4 V Vctrl window.  This isolates the pump's delivered charge
    from the loop filter's response to it (#10).
  - \`rshunt = 1e12\` is set: a disabled trim leg's cascode mid-node is driven
    only by two off devices and is floating for the DC solution.  The shunt
    contributes 3.3 pA at 3.3 V, below the abstol floor of the measurement.
  - **Limitation (feedback-edge contract with #11 not closed here)**: FB is
    driven as an idealized buffered edge.  DR-001 Decision 3 specifies that the
    real FB is a VCO edge retimed by one flop's clk->Q, shaped to be at least
    as wide as this PFD's reset delay.  This record REPORTS that reset delay
    (\`wmin_zero\` below) so #11 has a number to size its retiming pulse
    against; it does not verify the contract from the divider side.
  - **Limitation (nominal skew only)**: \`sw_stat_global = sw_stat_mismatch =
    0\`.  Random device mismatch on the charge pump is #15's campaign
    (\`mc-cp-mismatch\`); this record's \`q_zero\` is the SYSTEMATIC residue,
    which is the number that campaign's distribution should be centred on.$(method_note)
- **Statistical convention**: N/A -- corner-matrix claim, not a distribution
  claim.
- **Result**: ${NCHK} PVT corners checked; ${NFAIL} corner(s) failed the
  dead-zone criterion.

  | Corner | kd_near (A) | kd_wide (A) | ratio | wmin@0 (s) | q@0 (C) | t_offset (s) |
  |---|---|---|---|---|---|---|
${CORNER_TABLE}

  - Detector gain across corners: \`kd_wide\` from ${KDMIN} A to ${KDMAX} A
  - Minimum UP/DN pulse width at zero phase error (= PFD reset delay):
    ${WMIN} s to ${WMAX} s across corners
  - Worst linearity ratio: ${WORST_RATIO} at \`${WORST_CORNER}\`
  - Largest residual charge at zero phase error: ${QOFF} C at \`${QOFF_C}\`,
    equivalent to a static phase offset of ${TOFF} s at \`${TOFF_C}\`
  - **Overall: ${VERDICT}** on the dead-zone criterion (ratio > 0.5 and both
    UP/DN pulses present at dphi = 0, at every corner).
  Full tables: \`sim/pfd-deadzone/corners/${RID}/pfd_deadzone.csv\` (every
  (corner, dphi) point) and \`pfd_deadzone_verdict.csv\` (the per-corner
  verdict above, machine-readable).
- **Links**:
  - Testbench: \`sim/pfd-deadzone/testbench/tb_pfd_deadzone.sp\`,
    \`sim/pfd-deadzone/testbench/run.sh\`
  - Design: \`design/pfd_cp.sch\`, \`design/pfd.sch\`, \`design/cp.sch\`
  - Netlist snapshot: \`sim/pfd-deadzone/netlist-snapshots/${RID}.spice\`
  - Raw logs: \`sim/pfd-deadzone/corners/${RID}/\`
  - Extracted metrics: \`sim/pfd-deadzone/corners/${RID}/pfd_deadzone.csv\`,
    \`sim/pfd-deadzone/corners/${RID}/pfd_deadzone_verdict.csv\`
$(author_field)
$(supersedes_field)
EOF
} >"${RECORD}"

echo "pfd-deadzone: wrote ${RECORD}"
echo "pfd-deadzone: wrote ${OUT_SUMMARY}"
echo "pfd-deadzone: wrote ${CORNERSDIR}/ (${NPOINTS} corner logs)"
