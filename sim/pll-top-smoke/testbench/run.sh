#!/usr/bin/env bash
# gf180-pll :: pll-top-smoke :: closed-loop acceptance gate for design/pll_top.sch
#
# ONE nominal-corner run of the WHOLE loop, cold start, one N.  It exists to
# answer exactly one question -- "do the five blocks, wired together as
# design/pll_top.sch, form a loop that acquires and holds lock?" -- and it is
# the acceptance gate for #52's top-level assembly.  It is deliberately NOT a
# PVT campaign, and its record says so in its own Corner matrix field:
#
#   #12  sim/lock-time, sim/output-range   lock time / band coverage over PVT
#   #13  sim/period-jitter                 jitter
#   #14  sim/supply-sensitivity            supply pushing, power
#
# Those campaigns build their DUT through the same
# sim/lib/assemble_closed_loop.sh this runner uses, so there is one assembled
# top level in the repo rather than one per campaign.
#
# Usage:
#   ./run.sh                 # run and mint a record
#   ./run.sh --check         # run, print the metrics, write NO record
#   SIM_FORCE=1 ./run.sh     # ignore the cached run in work/ and re-simulate
#
#   SIM_SUPERSEDES=<record-id> SIM_SUPERSEDES_NOTE='<why>' ./run.sh
#                            mint with a **Supersedes** field naming the record
#                            this run replaces (sim/README.md :: "Status /
#                            supersession language").  Set at mint time on
#                            purpose -- editing the field into an already
#                            generated record is itself a record rewrite.
#
# The DUT netlist comes from design/netlist/pll_top.spice, exported by
# design/netlist.sh from design/pll_top.sch.  This runner freezes whatever is
# committed there; it does not regenerate it.  Run `design/netlist.sh --check`
# first if the schematics may have moved.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP="$(cd "${HERE}/.." && pwd)"
ROOT="$(cd "${EXP}/../.." && pwd)"
# shellcheck source=../../lib/simenv.sh
. "${ROOT}/sim/lib/simenv.sh"
# shellcheck source=../../lib/pll_top_dut.sh
. "${ROOT}/sim/lib/pll_top_dut.sh"

WORK="${EXP}/work"
DUT="${WORK}/dut_smoke.sp"

CHECK=0
[ "${1:-}" != "--check" ] || CHECK=1

# ---------------------------------------------------------------------------
# The operating point, and where every one of these numbers comes from.
# ---------------------------------------------------------------------------
# KFREF   2 MHz reference.  Inside DR-002 Decision 1's ratified 1-25 MHz range,
#         and near its low end on purpose: the loop's unity-gain frequency goes
#         as Icp*R*f_ref, so a low reference is the SLOW end of acquisition --
#         the demanding direction for a "does it lock at all" gate.
# KN      N = 8.  Mid of the ratified 4-64 range, and it exercises three active
#         div23 cells plus the retiming flop rather than the degenerate
#         two-cell minimum.
# KBAND   VCO band 2.  sim/vco-tuning-range record 20260731-175947-0a12e6c has
#         band 2 covering 10.9 .. 25.2 MHz at typical/27C/3.30V, so the
#         N*f_ref = 16 MHz target lands at Vctrl ~ 1.4 V -- the middle of
#         DR-001 Decision 2's usable 0.9-2.4 V control window, not at an edge
#         where a band-choice error would masquerade as a loop failure.
# KTRIM   Icp trim code 2 (three unit legs, ~5.2 uA), the nominal setting
#         design/README.md characterises the charge pump at.
KFREF=2e6
KN=8
KBAND=2
KTRIM=2

# KTSTOP  80 us of transient.  The control node has to slew from 0 V to the
#         ~1.4 V lock point through the loop filter's 122 pF, and then the
#         loop's own settling follows; 80 us leaves margin over both, and the
#         measurement windows below leave 14 us of run after the last one.
# KTMAX   500 ps ceiling on the internal timestep.  Set by the CHARGE PUMP, not
#         by the VCO: the PFD's minimum UP/DN pulse is 1.1-1.9 ns (the
#         24-inverter reset chain, design/README.md), and the charge delivered
#         in those pulses IS the loop gain, so the pulse has to be resolved by
#         several timesteps or the loop dynamics are an artefact of the
#         integration.  The VCO period at 16 MHz is 62 ns, i.e. this is ~125
#         points per output cycle, far finer than the output waveform needs.
# KTSTEP  20 ns print step (also the granularity of the committed waveform CSV
#         after decimation).  It does not limit `.meas` resolution: ngspice
#         measures against the internal timesteps, not the print step.
KTSTOP=80u
KTSTEP=20n
KTMAX=500p

# The two instants the lock criterion is evaluated at.  Both are placed on a
# reference HALF-period (tstart + (k + 0.5)/f_ref, with tstart = 0.5/f_ref), so
# "the first REF rise after t" and "the first FB rise after t" are the same
# cycle's pair and the phase measurement cannot alias by a whole reference
# period.  With f_ref = 2 MHz: tstart = 0.25 us, so 46.0 us = k=91 and
# 66.0 us = k=131.
#   KTA  46 us  -- the loop must already be locked here
#   KTB  66 us  -- 20 us later, leaving 14 us of run for the frequency
#                  measurements (160 VCO cycles = 10 us, 20 FB cycles = 10 us)
KTA=46.0u
KTB=66.0u

# Decimation of the committed waveform CSV, seconds.
KDECIM=20e-9

# Corner: nominal.  Every passive axis is named explicitly rather than left to
# default, because sim/README.md warns that a MOS-only sweep silently pins the
# passives at typical -- and this DUT contains the loop filter, whose R and C
# set the loop bandwidth directly.  Here they ARE all typical; the point is
# that the record says so because the run said so.
CORNER_BUNDLE="typical"
CORNER_LIBS="typical,res_typical,moscap_typical,mimcap_typical"
CORNER_TEMP=27
CORNER_VDD=3.30

# Acceptance thresholds.  Stated here, not discovered from the result.
ACC_FERR=1e-3          # |residual fractional frequency error|
ACC_PHI_FRAC=0.02      # |static phase error| as a fraction of a reference period
ACC_NTOL=0.01          # |measured f_out/f_fb - N|
ACC_LOCK_FRAC=0.90     # LOCK level in the late window, as a fraction of the rail
ACC_VCTRL_LO=0.9       # DR-001 Decision 2's usable control window
ACC_VCTRL_HI=2.4

# ---------------------------------------------------------------------------
simenv_require_tools

TAG="smoke_${CORNER_BUNDLE}_T${CORNER_TEMP}_V${CORNER_VDD/./p}_N${KN}_B${KBAND}"
CID="$(simenv_corner_id "${CORNER_BUNDLE}" "${CORNER_TEMP}" "${CORNER_VDD}")"

mkdir -p "${WORK}"
cloop_assemble "${HERE}/tb_pll_smoke.sp" "${DUT}"

PARAMS=(
  "vsup=${CORNER_VDD}"
  "fref=${KFREF}"
  "nratio=${KN}"
  "tstop=${KTSTOP}"
  "tstep=${KTSTEP}"
  "tmax=${KTMAX}"
  "ta=${KTA}"
  "tb=${KTB}"
)
# Word splitting of each helper's `name=value ...` line is exactly what is
# wanted here: one array element per .param.
# shellcheck disable=SC2207
PARAMS+=( $(cloop_band_params "${KBAND}") )
# shellcheck disable=SC2207
PARAMS+=( $(cloop_trim_params "${KTRIM}") )
# shellcheck disable=SC2207
PARAMS+=( $(cloop_divider_params "${KN}") )

RUNDIR="${WORK}/${TAG}"
LOG="${RUNDIR}/ngspice.log"
SIG="${CORNER_LIBS}|${CORNER_TEMP}|${PARAMS[*]}"

# A single 80 us closed-loop transient is a long run on a shared machine, so it
# is resumable -- but only on an EXACT match of the deck's mtime and the full
# argument list, never on the deck alone.  Reusing a run taken at different
# parameters is precisely the quiet-wrong-number failure sim/README.md exists
# to prevent.  SIM_FORCE=1 forces a cold run.
if [ -z "${SIM_FORCE:-}" ] && [ -f "${LOG}" ] && [ "${LOG}" -nt "${DUT}" ] \
   && [ "$(cat "${RUNDIR}/.sig" 2>/dev/null)" = "${SIG}" ] \
   && grep -q "Total analysis time" "${LOG}" 2>/dev/null; then
  echo "pll-top-smoke: reusing the completed run in ${RUNDIR}"
else
  echo "pll-top-smoke: simulating ${TAG} (${KTSTOP} transient -- this takes tens of minutes)"
  simenv_run_deck "${DUT}" "${WORK}" "${TAG}" "${CORNER_LIBS}" "${CORNER_TEMP}" "${PARAMS[@]}" \
    >/dev/null 2>&1 || true
  grep -q "Total analysis time" "${LOG}" 2>/dev/null || {
    echo "ERROR: ngspice did not complete the transient (see ${LOG})" >&2
    exit 1
  }
  printf '%s' "${SIG}" >"${RUNDIR}/.sig"
fi

# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
m() { simenv_meas "${LOG}" "$1"; }

PHI_A=$(m phi_a);       PHI_B=$(m phi_b)
DPHI=$(m dphi);         FERR=$(m ferr)
FOUT=$(m fout);         FFB=$(m ffb);        NMEAS=$(m nmeas)
VC_AVG=$(m vctrl_avg);  VC_MIN=$(m vctrl_min); VC_MAX=$(m vctrl_max)
VC_INI=$(m vctrl_ini)
T_LOCK=$(m t_lock);     LOCK_LVL=$(m lock_lvl)
I_REF=$(m i_ref);       I_VCO=$(m i_vco);    I_DIV=$(m i_div)

read -r V_FERR V_PHI V_N V_FOUT V_LOCK V_VCTRL VERDICT NLOCK <<EOF
$(awk -v ferr="${FERR}" -v phib="${PHI_B}" -v nmeas="${NMEAS}" -v fout="${FOUT}" \
      -v lock="${LOCK_LVL}" -v vcmin="${VC_MIN}" -v vcmax="${VC_MAX}" \
      -v fref="${KFREF}" -v n="${KN}" -v vdd="${CORNER_VDD}" \
      -v accf="${ACC_FERR}" -v accp="${ACC_PHI_FRAC}" -v accn="${ACC_NTOL}" \
      -v accl="${ACC_LOCK_FRAC}" -v vlo="${ACC_VCTRL_LO}" -v vhi="${ACC_VCTRL_HI}" '
BEGIN {
  tref = 1.0 / fref; ftarget = n * fref;
  a = (ferr  <= 0 ? -ferr : ferr)  <= accf                       ? "PASS" : "FAIL";
  b = (phib  <= 0 ? -phib : phib)  <= accp * tref                ? "PASS" : "FAIL";
  d = nmeas == "nan" ? "FAIL" :
      ((nmeas - n <= 0 ? n - nmeas : nmeas - n) <= accn          ? "PASS" : "FAIL");
  e = fout == "nan" ? "FAIL" :
      (((fout - ftarget <= 0 ? ftarget - fout : fout - ftarget) / ftarget) <= accf ? "PASS" : "FAIL");
  f = lock >= accl * vdd                                         ? "PASS" : "FAIL";
  g = (vcmin >= vlo && vcmax <= vhi)                             ? "PASS" : "FAIL";
  nf = 0;
  if (a == "FAIL") nf++; if (b == "FAIL") nf++; if (d == "FAIL") nf++;
  if (e == "FAIL") nf++; if (f == "FAIL") nf++; if (g == "FAIL") nf++;
  printf "%s %s %s %s %s %s %s %d\n", a, b, d, e, f, g,
         (nf == 0 ? "PASS" : "FAIL"), nf;
}')
EOF

FTARGET=$(awk -v f="${KFREF}" -v n="${KN}" 'BEGIN{printf "%.6g", f*n}')
VC_RIPPLE=$(awk -v a="${VC_MAX}" -v b="${VC_MIN}" 'BEGIN{printf "%.4g", a-b}')
PHI_B_NS=$(awk -v v="${PHI_B}" 'BEGIN{printf "%.4g", v*1e9}')
DPHI_NS=$(awk -v v="${DPHI}"  'BEGIN{printf "%.4g", v*1e9}')
FOUT_ERR_PPM=$(awk -v f="${FOUT}" -v t="${FTARGET}" 'BEGIN{printf "%.4g", (f-t)/t*1e6}')
P_TOT_MW=$(awk -v a="${I_REF}" -v b="${I_VCO}" -v c="${I_DIV}" -v v="${CORNER_VDD}" \
  'BEGIN{s=(a<0?-a:a)+(b<0?-b:b)+(c<0?-c:c); printf "%.4g", s*v*1e3}')

cat <<EOF
pll-top-smoke @ ${CID}  (N=${KN}, band ${KBAND}, Icp code ${KTRIM}, f_ref=${KFREF} Hz)
  target f_out            ${FTARGET} Hz
  measured f_out          ${FOUT} Hz   (${FOUT_ERR_PPM} ppm)        ${V_FOUT}
  measured f_fb           ${FFB} Hz
  measured N (f_out/f_fb) ${NMEAS}                                  ${V_N}
  residual freq error     ${FERR}  (phase drift over ${KTA}..${KTB}) ${V_FERR}
  static phase error      ${PHI_B_NS} ns  (drift ${DPHI_NS} ns)     ${V_PHI}
  Vctrl  start / settled  ${VC_INI} V / ${VC_AVG} V (ripple ${VC_RIPPLE} V) ${V_VCTRL}
  LOCK flag  first / late ${T_LOCK} s / ${LOCK_LVL} V               ${V_LOCK}
  supply  ref/vco/div     ${I_REF} / ${I_VCO} / ${I_DIV} A  (${P_TOT_MW} mW)
  OVERALL                 ${VERDICT}  (${NLOCK} check(s) failed)
EOF

if [ "${CHECK}" -eq 1 ]; then
  echo "pll-top-smoke: --check, no record written"
  exit 0
fi

# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------
RID="$(simenv_record_id)"
SNAPDIR="${EXP}/netlist-snapshots"; mkdir -p "${SNAPDIR}"
CORNERSDIR="${EXP}/corners/${RID}";  mkdir -p "${CORNERSDIR}"
RECORDSDIR="${EXP}/records";         mkdir -p "${RECORDSDIR}"

cp "${DUT}" "${SNAPDIR}/${RID}.spice"
SHA="$(simenv_sha256 "${SNAPDIR}/${RID}.spice")"
simenv_archive_log "${WORK}" "${TAG}" "${CORNERSDIR}" "${CID}"

# Decimated acquisition waveform.  sim/README.md's waveform rule: the transient
# IS the argument here, so keep the trace -- as a decimated CSV of the signals
# that carry it, never as the rawfile.
WAVE="${CORNERSDIR}/lock_transient_${CID}.csv"
{
  echo "# gf180-pll :: pll-top-smoke acquisition transient"
  echo "# record_id: ${RID}"
  echo "# corner: ${CID} (${CORNER_LIBS})"
  echo "# config: N=${KN} band=${KBAND} icp_code=${KTRIM} fref=${KFREF}"
  echo "# decimation: nearest-sample at ${KDECIM} s from the full ngspice trace"
  echo "t_s,vctrl_v,lock_v,fb_v"
  # ngspice `wrdata` writes one (time, value) column PAIR per vector, so the
  # columns are t,vctrl,t,lock,t,fb.  Nearest-sample decimation: keep the first
  # sample at or after each multiple of KDECIM.  No interpolation, so every row
  # in the committed CSV is a value ngspice actually computed.
  awk -v d="${KDECIM}" '
    /^[ \t]*[-0-9]/ {
      t = $1 + 0;
      if (t + 1e-15 >= next_t) {
        printf "%.9g,%.6g,%.6g,%.6g\n", t, $2, $4, $6;
        next_t = t + d;
      }
    }' "${RUNDIR}/lock_transient_full.csv"
} >"${WAVE}"
WAVEROWS=$(grep -vc '^#' "${WAVE}")

cat >"${RECORDSDIR}/${RID}.md" <<EOF
# Record ${RID}

- **Record ID**: ${RID}
- **Claim**: #52 (design-input claim, not a spec line) -- do the five blocks of
  \`design/pll_top.sch\` -- \`pfd_cp\` (#9), \`loop_filter\` (#10), \`vco\` (#8),
  \`divider_chain\` and \`lock_detector\` (#11) -- wired per DR-001's type-II
  charge-pump architecture, form a loop that ACQUIRES and HOLDS lock from a
  cold start? This is the acceptance gate for the top-level assembly landing
  in \`design/\`, and nothing more: it is one corner, one N, one band. It does
  **not** substantiate any spec line, and it is not a substitute for #12
  (\`lock-time\`, \`output-range\`), #13 (\`period-jitter\`) or #14
  (\`supply-sensitivity\`), each of which owns a PVT campaign against this same
  assembled DUT.
- **Netlist provenance**: schematic (\`design/pll_top.sch\`, exported by
  \`design/netlist.sh\` to \`design/netlist/pll_top.spice\`) ->
  \`sim/pll-top-smoke/netlist-snapshots/${RID}.spice\` (exported subcircuit +
  testbench, concatenated by \`sim/lib/assemble_closed_loop.sh\`), SHA-256
  \`${SHA}\`
- **Environment provenance**:
$(simenv_env_block "$(simenv_xschem_version) -- the DUT
    netlist is an xschem export of design/pll_top.sch, not a hand-written deck.")
- **Corner matrix run**: **1 point** -- \`${CORNER_BUNDLE}\` / ${CORNER_TEMP} C /
  ${CORNER_VDD} V, the nominal corner.
  - Bundle -> \`.lib\` sections of \`sm141064.ngspice\`: \`${CORNER_BUNDLE}\` ->
    ${CORNER_LIBS//,/, } (every passive axis named explicitly, not defaulted:
    the DUT contains the loop filter, whose poly resistor, MOS caps and MIM cap
    set the loop bandwidth directly -- \`sim/README.md\` warns that a MOS-only
    sweep silently pins those at typical, so this record states that they are
    at typical **because the run put them there**)
  - Temperature: 27 C only. Supply: ${CORNER_VDD} V only. Process: \`typical\`
    only.
  - **Axes not swept, and why.** This is a one-point run by design, and
    \`sim/README.md\` requires the reason rather than the fact. The question
    this record answers is a **connectivity and closed-loop-existence**
    question about a newly assembled top level -- "is the loop wired such that
    it acquires and holds lock" -- not a performance question. A performance
    number needs the grid; "does the assembly close the loop" is answered, or
    not answered, at any single corner, and answering it at 45 is 45x the
    wall clock for no additional information about the wiring. Every
    performance claim over this DUT is explicitly deferred to the campaigns
    named in the Claim field, each of which carries the full grid. **This
    record must not be cited for any PVT claim.**
  - N: ${KN} only (of the ratified 4-64). Band code: ${KBAND} of 8. Icp trim
    code: ${KTRIM} of 4. Reference: ${KFREF} Hz of the ratified 1-25 MHz range.
- **Methodology / criteria / limitations**:
  - **DUT assembly**: \`design/netlist/pll_top.spice\` (the committed export of
    \`design/pll_top.sch\`) prepended to
    \`sim/pll-top-smoke/testbench/tb_pll_smoke.sp\` by
    \`sim/lib/assemble_closed_loop.sh\`, which is the single assembly path
    every closed-loop campaign in this repo uses. The DUT is not
    hand-transcribed anywhere: a schematic edit this deck does not track is a
    netlist error, not a divergent second copy of the design.
  - **Cold start**: \`.ic v(vctrl) = 0\`, i.e. the VCO begins at its floor
    frequency (the fixed \`VFIX\` branch of the V->I converter, well below
    N*f_ref) and the loop has to pump the control node up to its lock point
    unaided. The VCO ring's DC symmetry is broken with the same \`.ic\` pattern
    \`sim/vco-tuning-range\` uses; \`uic\` is deliberately not used, so the
    constant-gm bias generator is solved to its operating point before t = 0
    and the run is loop acquisition rather than bias start-up.
  - **Lock criterion**, stated before the run and applied to it:
    1. **Frequency** -- the residual fractional frequency error, measured as
       the DRIFT of the REF->FB phase between t = ${KTA} and t = ${KTB},
       must be <= ${ACC_FERR}. In a type-II loop a residual frequency error
       makes the static phase slip linearly at exactly (df/f) seconds per
       second, so differencing one phase measurement against another 20 us
       later measures it directly, to picosecond resolution and with no
       dependence on how many cycles the simulator put in between.
    2. **Phase** -- the static REF->FB phase error at t = ${KTB} must be
       <= ${ACC_PHI_FRAC} of a reference period.
    3. **Ratio** -- f_out / f_fb, measured independently over 160 whole VCO
       cycles and 20 whole feedback cycles, must equal N to within
       ${ACC_NTOL}, so a divider dividing by the wrong N shows up as a ratio
       error rather than hiding inside a single frequency reading.
    4. **Absolute output** -- f_out must be within ${ACC_FERR} of N*f_ref.
    5. **The block's own LOCK flag** must sit above ${ACC_LOCK_FRAC} of the
       rail through the late window (averaged, so a chattering flag reads as a
       fraction rather than being rounded to a verdict).
    6. **Control node in range** -- Vctrl must stay inside DR-001 Decision 2's
       usable ${ACC_VCTRL_LO}-${ACC_VCTRL_HI} V window, so a "lock" achieved by
       running the V->I converter off the end of its range is not counted.
    Both phase instants are placed on a reference half-period, so "the first
    REF rise after t" and "the first FB rise after t" are the same cycle's
    pair and the measurement cannot alias by a whole reference period.
  - **Simulator settings**: \`.tran ${KTSTEP} ${KTSTOP} 0 ${KTMAX}\`,
    \`reltol 1e-3\`, \`abstol 1e-13\`, \`vntol 1e-6\`, \`rshunt 1e12\`,
    \`itl4 200\`. The ${KTMAX} timestep ceiling is set by the CHARGE PUMP, not
    by the VCO: the PFD's minimum UP/DN pulse is 1.1-1.9 ns and the charge
    delivered in those pulses is the loop gain, so the pulse must be resolved
    by several timesteps or the loop dynamics become an artefact of the
    integration. \`rshunt\` and \`itl4\` carry over from \`sim/pfd-deadzone\`
    for the same reasons documented there (floating cascode mid-nodes on the
    disabled trim legs; the dump-node buffer's two MOS gates on the control
    node).
  - **Waveform retained**: the acquisition transient is the argument here, so
    it is kept -- decimated to ${KDECIM} s per sample (${WAVEROWS} rows) as
    \`corners/${RID}/lock_transient_${CID}.csv\`, never as a rawfile. The deck
    regenerates the full trace.
  - **Limitations**:
    - **Schematic-level, no parasitics.** Every block's own record carries the
      same caveat; #18 owns the extracted re-run.
    - **Ideal bias.** \`IBN\`/\`ICN\`/\`IBP\`/\`ICP\` are driven from ideal
      current sources at 4x the unit-leg current, as every charge-pump campaign
      in this repo does. The bias generator is a separate, unbuilt block; its
      mismatch is additive to the budget in \`design/README.md\` and is not in
      any number here.
    - **Ideal reference.** A pulse source with 200 ps edges and no jitter. The
      reference's own noise is not in this result.
    - **One point is one point.** Nothing here says anything about lock time,
      jitter, spurs, power or band coverage over PVT, and the numbers below
      must not be quoted as if it did.
  - Statistical switches: \`sw_stat_global = sw_stat_mismatch = 0\` (nominal
    per-corner skew, no Monte Carlo mismatch).
- **Statistical convention**: N/A -- this is a single deterministic run, not a
  distribution claim. Charge-pump device mismatch, which sets the static phase
  offset, is #15's \`mc-cp-mismatch\` campaign.
- **Result**:

  | # | Check | Criterion | Measured | Verdict |
  |---|---|---|---|---|
  | 1 | residual frequency error (phase drift ${KTA} -> ${KTB}) | <= ${ACC_FERR} | ${FERR} | **${V_FERR}** |
  | 2 | static phase error, REF -> FB, at ${KTB} | <= ${ACC_PHI_FRAC} of a reference period | ${PHI_B_NS} ns | **${V_PHI}** |
  | 3 | divide ratio f_out / f_fb | ${KN} +/- ${ACC_NTOL} | ${NMEAS} | **${V_N}** |
  | 4 | output frequency vs N*f_ref = ${FTARGET} Hz | within ${ACC_FERR} | ${FOUT} Hz (${FOUT_ERR_PPM} ppm) | **${V_FOUT}** |
  | 5 | block LOCK flag, late-window average | >= ${ACC_LOCK_FRAC} of the rail | ${LOCK_LVL} V | **${V_LOCK}** |
  | 6 | Vctrl inside the usable window | ${ACC_VCTRL_LO} .. ${ACC_VCTRL_HI} V | ${VC_MIN} .. ${VC_MAX} V | **${V_VCTRL}** |

  Supporting numbers (reported, not gated):

  | Quantity | Value |
  |---|---|
  | Vctrl at the start of the run (cold) | ${VC_INI} V |
  | Vctrl settled, late-window average | ${VC_AVG} V |
  | Vctrl peak-to-peak ripple, late window | ${VC_RIPPLE} V |
  | LOCK flag first asserts at | ${T_LOCK} s |
  | phase error at ${KTA} / at ${KTB} | ${PHI_A} s / ${PHI_B} s |
  | feedback frequency f_fb | ${FFB} Hz |
  | supply current, ref / vco / div domain | ${I_REF} / ${I_VCO} / ${I_DIV} A |
  | total power at this corner | ${P_TOT_MW} mW |

  **Overall: ${VERDICT}** (${NLOCK} of 6 checks failed).

  The Vctrl ripple and the supply/power figures are here because a loop that
  "locks" while drawing an implausible current, or while the control node
  swings across its whole window every reference cycle, is not actually
  working -- not because this record substantiates a ripple, spur or power
  claim. It does not; #14 does.
- **Links**:
  - Testbench: \`sim/pll-top-smoke/testbench/tb_pll_smoke.sp\`
  - Assembly: \`sim/lib/assemble_closed_loop.sh\`
  - Schematic: \`design/pll_top.sch\`
  - Netlist snapshot: \`sim/pll-top-smoke/netlist-snapshots/${RID}.spice\`
  - Raw log: \`sim/pll-top-smoke/corners/${RID}/${CID}.log\`
  - Acquisition transient: \`sim/pll-top-smoke/corners/${RID}/lock_transient_${CID}.csv\`
- **Timestamp / author**: $(date -u +%Y-%m-%dT%H:%M:%SZ), agent-builder (issue #52)
$(simenv_supersedes_field "${SIM_SUPERSEDES:-}")
EOF

echo "pll-top-smoke: wrote ${RECORDSDIR}/${RID}.md"
echo "pll-top-smoke: wrote ${WAVE} (${WAVEROWS} rows)"
echo "pll-top-smoke: OVERALL ${VERDICT}"
[ "${VERDICT}" = "PASS" ] || exit 1
