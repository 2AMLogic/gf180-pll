#!/usr/bin/env bash
# gf180-pll :: pll-top-smoke :: closed-loop acceptance gate for design/pll_top.sch
#
# ONE nominal-corner run of the WHOLE loop, one N.  It exists to answer exactly
# one question -- "do the five blocks, wired together as design/pll_top.sch,
# form a loop that acquires and holds lock?" -- and it is the acceptance gate
# for #52's top-level assembly.  It is deliberately NOT a PVT campaign, and not
# a lock-TIME measurement either; its record says so in its own Corner matrix
# field:
#
#   #12  sim/lock-time, sim/output-range   lock time / band coverage over PVT
#   #13  sim/period-jitter                 jitter
#   #14  sim/supply-sensitivity            supply pushing, power
#
# #14 builds its DUT through the same sim/lib/pll_top_dut.sh this runner uses,
# so those two campaigns share one assembled top level.  #12's two campaigns do
# NOT yet: they predate design/pll_top.sch and build a closed loop by
# concatenating the individual block exports (sim/lib/assemble_closed_loop.sh,
# a different helper with a similar name -- see sim/lib/pll_top_dut.sh's header
# and sim/README.md, "Closed-loop campaigns: two assembly paths").  Converging
# them onto this assembly is follow-up work, not a thing this file may claim.
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
# Every frequency below is read out of this repo's own evidence, not assumed:
# `sim/vco-tuning-range/corners/20260731-175947-0a12e6c/kvco_by_point.csv`,
# rows `typical,27,3.30`, is the f(Vctrl) table for the exact corner this
# campaign runs at, and `sim/loop-dynamics/records/20260731-195707-3e3814c.md`
# is where R = 77.11 kOhm, C1 = 120.8 pF and C2 = 2.016 pF come from.
#
# KFREF   9 MHz reference, inside DR-002 Decision 1's ratified 1-25 MHz range.
# KN      N = 8.  Mid of the ratified 4-64 range, and it exercises three active
#         div23 cells plus the retiming flop rather than the degenerate
#         two-cell minimum.
# KBAND   VCO band 5.  The N*f_ref = 72 MHz target sits at Vctrl = 1.50 V in
#         band 5 (measured 72.25 MHz there), squarely mid-window in DR-001
#         Decision 2's usable 0.9-2.4 V range.  Band 5 is also the LOWEST band
#         that reaches 72 MHz *inside* that window, which is the band-selection
#         rule the vco-tuning-range record states (a lower band reaches a given
#         frequency only near the top of its Vctrl range, where its Kvco is
#         already large): band 4 tops out at 72.69 MHz and would need Vctrl
#         ~2.68 V, outside the usable window.  Kvco here is 39.7 MHz/V, far
#         under DR-001's ~150 MHz/V fixed-filter ceiling.
# KTRIM   Icp trim code 2 (three unit legs, ~5.2 uA), the nominal setting
#         design/README.md characterises the charge pump at.
#
# Why 72 MHz and not the bottom of the output band.  NOT because of in-lock
# ripple.  That is what this file argued until #70, from Icp*R -- the charge
# pump driving its full Icp into R = 77.11 kOhm, "roughly +/-0.39 V of ripple
# in lock, by construction" -- and it is wrong by more than an order of
# magnitude, in a direction that matters (it makes the filter look far worse
# than it is).  Icp*R is the voltage the control node would REACH, not the one
# it does reach: the charge lands on C2, and the node only climbs to Icp*R if
# the pulse lasts long compared with R*C2 = 77.11 kOhm * 2.016 pF = 155 ns.
# No pulse can -- the reference period itself is 111 ns.  For t_p << R*C2 the
# step is Icp*t_p/C2, and in lock t_p is only the PFD's reset-delay overlap
# (1.1-1.9 ns, design/README.md's 24-inverter reset chain) with UP and DN both
# asserted, so what actually reaches the node is not Icp*t_p but the pump's
# residual charge asymmetry |q_up + q_dn|.  DR-006 Decision 8 carries that
# number through THIS filter from sim/cp-compliance record
# 20260731-194124-afa338c: 3.68 fC worst corner / 2.16 fC median, i.e.
# dQ/C2 = 1.83 mV / 1.07 mV of peak control-line ripple in lock.  Millivolts.
#
# The superseded record 20260801-085349-0e5c22d is the arithmetic check on
# both halves of that.  It measured 29.5 mV peak-to-peak while still carrying
# a 14.05 ns static phase error, and Icp*t_p/C2 at t_p = 14.05 ns is 36 mV --
# so that 29.5 mV is a not-yet-locked loop pumping once per reference cycle,
# roughly 16-27x the ripple the same filter carries once the phase error is
# gone, and not a measurement of in-lock ripple at all.
#
# What does set the lock point is (a) the band rule above -- band 5 is the
# lowest band reaching 72 MHz inside the 0.9-2.4 V window -- and (b) headroom
# for the ACQUISITION excursion, which is where the control node actually
# travels.  The same committed waveform visits 1.084 V within the first 60 ns
# (the `.ic` relaxing into the real network) and 1.537 V at 6.4 us, before
# settling at 1.496 V: 0.41 V below the eventual lock point and 0.04 V above
# it, 453 mV peak-to-peak.  That is ~15x the late-window figure and ~250x the
# in-lock ripple, and it -- not the ripple -- is what a lock point near either
# end of the window would push outside it, failing check 6 on a loop that goes
# on to lock perfectly well.
KFREF=9e6
KN=8
KBAND=5
KTRIM=2

# KVSTART The control node is released at 1.20 V, where band 5 runs at
#         60.7 MHz -- 16 % below the 72 MHz target, so the loop has a real
#         frequency error to null and the PFD has to frequency-detect its way
#         in, not merely settle a phase.  It is NOT released at 0 V, and that
#         is a deliberate scope line rather than a convenience: below the band
#         floor the VCO is outside the range `sim/vco-tuning-range`
#         characterised at all, so a 0 V release would put the first
#         (and longest) part of the run in territory no record covers.  It is
#         also the expensive part -- the control node slews at Icp/C1 =
#         5 uA / 120.8 pF = 41 mV/us, i.e. 24 us per volt, so where the node
#         starts sets the run length almost by itself.  **Cold-start lock TIME,
#         over PVT, is #12's campaign** (`sim/lock-time`); this one answers
#         only whether the assembled loop closes.
# KTSTOP  56 us of transient.  This file carried 20 us until #70, from adding
#         0.30 V of slewing at 41 mV/us (7.3 us) to "about 5 time constants at
#         f_c = 284 kHz" (2.8 us).  The second term is the error, and it is a
#         systematic one rather than a slip: f_c is the loop's CROSSOVER
#         frequency, and this loop is deliberately overdamped, so what sets its
#         settling is the dominant CLOSED-LOOP pole -- which sits near
#         1/(2*pi*R*C1) = 17.09 kHz, a 9.31 us time constant, 3.3x slower than
#         1/(2*pi*f_c).  That is not a new finding here: it is exactly why
#         spec/pll.md's Lock time section states a STRUCTURAL settling floor of
#         ~43 us "regardless of how much Icp is applied", and why DR-006
#         Decision 7 dropped the <20 us stretch target from the ratified spec
#         rather than carrying it.  A 20 us transient is less than HALF that
#         ratified floor: it was asking this loop for something the spec
#         already says it cannot do, and the superseded record
#         20260801-085349-0e5c22d is what that looks like -- four FAILs that
#         are four views of one fact, a loop still converging at tstop.
#
#         That record also MEASURES the time constant, and it agrees with the
#         filter: the REF->FB phase error went 19.57 ns at 14 us -> 14.05 ns at
#         17 us, i.e. an exponential with tau = 3 us / ln(19.57/14.05) =
#         9.05 us against the 9.31 us R*C1 predicts.  Extrapolating that same
#         decay is how the window below is placed.  56 us is tb + 3 us, which
#         leaves the late-window measurements the run they need (160 whole VCO
#         cycles = 2.2 us, 20 whole FB cycles = 2.2 us).
#
#         The cost is real and is the reason 20 us was attractive: wall clock
#         scales with tstop at a fixed timestep ceiling, so this is ~2.8x the
#         4386 s the 20 us run took.  That is the price of measuring past the
#         filter's own settling floor instead of before it.
# KTMAX   100 ps ceiling on the internal timestep.  Set by the PFD's INTERNAL
#         SET PULSE -- not by the VCO, and not by the UP/DN output pulse either.
#         `design/edgedet.sch` fires each SR latch with AND(X, NOT(X delayed by
#         5 inverters)); that pulse measures 0.33-0.39 ns at typical/27C/3.30 V.
#         The UP/DN pulse it eventually produces is 1.1-1.9 ns wide (the
#         24-inverter reset chain, design/README.md) and reasoning from THAT
#         number is the trap: a 500 ps ceiling gives a mean internal step of
#         0.38 ns, so ngspice steps clean over the 0.35 ns set pulse on roughly
#         half of the feedback edges.  Every missed set is a feedback edge the
#         PFD never sees, so the loop reads as jammed with UP asserted and
#         Vctrl ramps to the rail while the feedback is ALREADY faster than the
#         reference -- a "the loop does not lock" result that is entirely an
#         artefact of the integration.  100 ps puts 3-4 steps inside the set
#         pulse.  Every closed-loop campaign (#12/#13/#14) inherits this bound;
#         it is a property of the PFD, not of this testbench.
# KTSTEP  20 ns print step (also the granularity of the committed waveform CSV
#         after decimation).  It does not limit `.meas` resolution: ngspice
#         measures against the internal timesteps, not the print step.
KVSTART=1.20
KTSTOP=56u
KTSTEP=20n
KTMAX=100p

# The two instants the lock criterion is evaluated at.  Both are placed on a
# reference HALF-period (tstart + (k + 0.5)/f_ref, with tstart = 0.5/f_ref), so
# "the first REF rise after t" and "the first FB rise after t" are the same
# cycle's pair and the phase measurement cannot alias by a whole reference
# period.  At f_ref = 9 MHz that makes every multiple of 1/9 us a legal
# instant: tstart = 55.556 ns, so 50 us is k = 449 and 53 us is k = 476, both
# exact.
#
#   KTA  50 us  -- the loop must already be locked here.  Placed from two
#                  numbers this repo already owns, not from where a verdict
#                  flips.  (i) spec/pll.md's ~43 us STRUCTURAL settling floor
#                  is the earliest instant at which any window may legitimately
#                  sit, because the ratified spec states the loop cannot settle
#                  faster than that.  (ii) The binding threshold among the
#                  seven checks is not check 2's 0.02*T_ref = 2.22 ns but the
#                  block's own LOCK FLAG: sim/lock-detector record
#                  20260731-095213-0bffe91 measures its comparator window at
#                  THIS corner as asserting up to 1.2 ns and not asserting from
#                  1.5 ns, and spec/pll.md sets the ratified lock criterion to
#                  1 ns for exactly that reason -- so the criterion and the
#                  on-chip observable describe the same event.  Extrapolating
#                  the superseded record's measured decay (14.05 ns at 17 us,
#                  tau = 9.05 us) puts the phase error near 0.4 ns at 50 us:
#                  ~3x inside the tightest of the seven criteria, and ~0.75 tau
#                  past the ratified floor.
#
#                  It does not go to zero, and that is why 50 us is a placement
#                  rather than "as late as affordable".  The charge pump's own
#                  static offset is the asymptote (-0.06 .. +0.67 ns over 45
#                  corners -- design/README.md, up/down mismatch budget term 4)
#                  and that asymptote already sits inside the detector window,
#                  so past this point waiting longer buys progressively less.
#   KTB  53 us  -- 3 us later, unchanged from the superseded record: ferr is a
#                  phase DRIFT across that interval, and 3 us of run is left
#                  after it for the frequency measurements (160 VCO cycles =
#                  2.2 us, 20 FB cycles = 2.2 us).
KTA=50.0u
KTB=53.0u

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
# Mean DN level in the late window, as a fraction of the rail.  In lock the DN
# branch pulses once per reference cycle for the PFD's reset delay, so the
# expected duty is (reset delay)*(f_ref) ~= 1.5 ns * 9 MHz = 1.4 %.  The floor
# below is more than 40x lower: it is not a measurement of the overlap, it is a
# guard that the DN branch asserts AT ALL -- see the note beside check 7.
ACC_DN_FRAC=3e-4

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
  "vstart=${KVSTART}"
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

# A single closed-loop transient at a 100 ps timestep ceiling is a long run on a
# shared machine, so it is resumable -- but only on an EXACT match of the deck's
# mtime and the full
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
UP_LVL=$(m up_lvl);     DN_LVL=$(m dn_lvl)
I_REF=$(m i_ref);       I_VCO=$(m i_vco);    I_DIV=$(m i_div)

# Every ternary below is kept on ONE line on purpose.  BWK awk (macOS's
# /usr/bin/awk) treats a `?:` split across a newline as a syntax error, which
# aborts the whole program and returns an EMPTY verdict table -- the checks then
# read as blank rather than PASS/FAIL, which is a silent loss of the gate.
read -r V_FERR V_PHI V_N V_FOUT V_LOCK V_VCTRL V_PFD VERDICT NLOCK <<EOF
$(awk -v ferr="${FERR}" -v phib="${PHI_B}" -v nmeas="${NMEAS}" -v fout="${FOUT}" \
      -v lock="${LOCK_LVL}" -v vcmin="${VC_MIN}" -v vcmax="${VC_MAX}" \
      -v dnl="${DN_LVL}" -v accd="${ACC_DN_FRAC}" \
      -v fref="${KFREF}" -v n="${KN}" -v vdd="${CORNER_VDD}" \
      -v accf="${ACC_FERR}" -v accp="${ACC_PHI_FRAC}" -v accn="${ACC_NTOL}" \
      -v accl="${ACC_LOCK_FRAC}" -v vlo="${ACC_VCTRL_LO}" -v vhi="${ACC_VCTRL_HI}" '
function num(x)  { return (x ~ /^-?[0-9]+\.?[0-9]*([eE][-+]?[0-9]+)?$/) }
function abs(x)  { return (x < 0 ? -x : x) }
BEGIN {
  tref = 1.0 / fref; ftarget = n * fref;
  # A measurement that did not land comes back as the literal "nan", and awk
  # would silently coerce that to 0 -- which would turn "the .meas failed" into
  # a PASS on any check whose criterion is an upper bound.  Every input is
  # therefore tested for being a number FIRST; a non-number is a FAIL, never a
  # zero.
  a = !num(ferr)  ? "FAIL" : (abs(ferr) <= accf                      ? "PASS" : "FAIL");
  b = !num(phib)  ? "FAIL" : (abs(phib) <= accp * tref               ? "PASS" : "FAIL");
  d = !num(nmeas) ? "FAIL" : (abs(nmeas - n) <= accn                 ? "PASS" : "FAIL");
  e = !num(fout)  ? "FAIL" : (abs(fout - ftarget) / ftarget <= accf  ? "PASS" : "FAIL");
  f = !num(lock)  ? "FAIL" : (lock >= accl * vdd                     ? "PASS" : "FAIL");
  g = (!num(vcmin) || !num(vcmax)) ? "FAIL" : ((vcmin >= vlo && vcmax <= vhi) ? "PASS" : "FAIL");
  # The PFD fires each SR latch from a 0.33-0.39 ns internal pulse, narrower
  # than the 1.1-1.9 ns UP/DN pulse it eventually produces.  A transient whose
  # timestep ceiling is set from the UP/DN width steps clean over the set
  # pulse, the PFD stops seeing feedback edges, and the loop reads as jammed
  # with UP asserted.  In a locked loop BOTH branches pulse once per reference
  # cycle for the reset-delay overlap, so a DN branch that never asserts is
  # proof the integration -- not the design -- failed.  Gated separately from
  # the lock checks because it distinguishes those two.
  h = !num(dnl) ? "FAIL" : (dnl >= accd * vdd ? "PASS" : "FAIL");
  nf = 0;
  if (a == "FAIL") nf++; if (b == "FAIL") nf++; if (d == "FAIL") nf++;
  if (e == "FAIL") nf++; if (f == "FAIL") nf++; if (g == "FAIL") nf++;
  if (h == "FAIL") nf++;
  printf "%s %s %s %s %s %s %s %s %d\n", a, b, d, e, f, g, h,
         (nf == 0 ? "PASS" : "FAIL"), nf;
}')
EOF

# Derived display quantities.  Each one propagates "nan" rather than letting
# awk coerce a failed measurement to 0 and print a plausible-looking number --
# an unsupported number in an evidence record is worse than a visible gap.
NUMRE='^-?[0-9]+\.?[0-9]*([eE][-+]?[0-9]+)?$'
numeric() { printf '%s' "$1" | grep -qE "${NUMRE}"; }

FTARGET=$(awk -v f="${KFREF}" -v n="${KN}" 'BEGIN{printf "%.6g", f*n}')
VC_RIPPLE=nan; PHI_B_NS=nan; DPHI_NS=nan; FOUT_ERR_PPM=nan; P_TOT_MW=nan
numeric "${VC_MAX}" && numeric "${VC_MIN}" && \
  VC_RIPPLE=$(awk -v a="${VC_MAX}" -v b="${VC_MIN}" 'BEGIN{printf "%.4g", a-b}')
numeric "${PHI_B}" && PHI_B_NS=$(awk -v v="${PHI_B}" 'BEGIN{printf "%.4g", v*1e9}')
numeric "${DPHI}"  && DPHI_NS=$(awk  -v v="${DPHI}"  'BEGIN{printf "%.4g", v*1e9}')
numeric "${FOUT}"  && FOUT_ERR_PPM=$(awk -v f="${FOUT}" -v t="${FTARGET}" \
  'BEGIN{printf "%.4g", (f-t)/t*1e6}')
numeric "${I_REF}" && numeric "${I_VCO}" && numeric "${I_DIV}" && \
  P_TOT_MW=$(awk -v a="${I_REF}" -v b="${I_VCO}" -v c="${I_DIV}" -v v="${CORNER_VDD}" \
    'BEGIN{s=(a<0?-a:a)+(b<0?-b:b)+(c<0?-c:c); printf "%.4g", s*v*1e3}')

# ---------------------------------------------------------------------------
# The record's CONCLUSION, generated rather than left to the reader.
# ---------------------------------------------------------------------------
# `sim/README.md` asks a design-input record for the conclusion drawn, not just
# the verdict, and a seven-row verdict table does not carry one.  "4 of 7
# failed" admits at least four incompatible readings -- the loop is miswired,
# the loop cannot lock, the integration never resolved the detector, or the
# transient simply ended before the loop arrived -- and nothing in the count
# separates them.  WHICH checks failed does separate them, because checks 3 and
# 7 are deliberately not lock criteria: 3 is the assembly guard (did the loop
# close through the configured N at all) and 7 is the integration guard (did
# the timestep resolve the PFD).  So the reading is emitted here, from the
# verdict pattern, instead of being reconstructed by whoever cites the record.
#
# This exists because the first record of this campaign,
# `20260801-085349-0e5c22d`, read **FAIL** without saying which of those four
# things it was -- and it was the fourth, a 20 us transient against a loop
# whose own filter cannot settle in under ~43 us (see KTSTOP above).  Records
# are immutable, so the fix has to live in the template: it appears on every
# record minted from here on and never retro-fits the one that motivated it.
#
# Wrapped by awk rather than by `fmt` on purpose -- BSD and GNU `fmt` disagree
# about where they break, and a record's line breaks should not depend on which
# host minted it.
wrap_para() {
  awk -v w=74 '{
    n = split($0, word, /[ \t]+/); line = "";
    for (i = 1; i <= n; i++) {
      if (word[i] == "") continue;
      if (line == "") { line = word[i]; continue }
      if (length(line) + 1 + length(word[i]) > w) { print "  " line; line = word[i] }
      else { line = line " " word[i] }
    }
    if (line != "") print "  " line;
  }'
}

record_conclusion() {
  # Direction of travel between the two phase instants.  This is the single
  # fact that separates "the window was early" from "the loop does not
  # converge", and neither the verdict nor the phase value alone carries it.
  local trend="at least one of the two phase instants did not land, so the direction of travel is unknown"
  if numeric "${PHI_A}" && numeric "${PHI_B}"; then
    trend=$(awk -v a="${PHI_A}" -v b="${PHI_B}" -v ta="${KTA}" -v tb="${KTB}" '
      function abs(x) { return (x < 0 ? -x : x) }
      BEGIN {
        if (abs(b) < 0.95 * abs(a))
          printf "the phase error was still SHRINKING across the measurement window (%.4g ns at %s, %.4g ns at %s) -- a converging loop caught before it arrived, not one that cannot converge", abs(a)*1e9, ta, abs(b)*1e9, tb;
        else if (abs(b) > 1.05 * abs(a))
          printf "the phase error GREW across the measurement window (%.4g ns at %s, %.4g ns at %s) -- divergence, not a window placed too early", abs(a)*1e9, ta, abs(b)*1e9, tb;
        else
          printf "the phase error was FLAT across the measurement window (%.4g ns at %s, %.4g ns at %s) -- the loop had settled to this offset rather than being caught mid-convergence", abs(a)*1e9, ta, abs(b)*1e9, tb;
      }')
  fi

  local s
  if [ "${VERDICT}" = "PASS" ]; then
    s="**Conclusion.** All seven checks pass, so this record answers its claim"
    s="${s} in the affirmative and closes the acceptance gate it was built for:"
    s="${s} the five blocks of \`design/pll_top.sch\`, wired as they are"
    s="${s} committed, form a loop that ACQUIRES lock from a real frequency"
    s="${s} error -- released at ${KVSTART} V, well below the lock point, so the"
    s="${s} PFD has to frequency-detect its way in rather than settle a small"
    s="${s} phase -- and HOLDS it. Each leg of that is measured, not inferred:"
    s="${s} the residual frequency error (${FERR}) and the static phase error"
    s="${s} (${PHI_B_NS} ns) say the phase is neither drifting nor offset; the"
    s="${s} independently measured divide ratio (${NMEAS}) says the loop closed"
    s="${s} through the configured N and not at some other ratio; the block's"
    s="${s} own LOCK flag (${LOCK_LVL} V late-window average) says the on-chip"
    s="${s} observable agrees with the criterion rather than describing a"
    s="${s} different event; and Vctrl (${VC_MIN} .. ${VC_MAX} V) says it did so"
    s="${s} from inside the usable control window rather than off the end of it."
    s="${s} Check 7, the integration guard, passes too (${DN_LVL} V mean on DN),"
    s="${s} so none of the above is an artefact of a timestep that stepped over"
    s="${s} the detector."
  else
    s="**Conclusion.** OVERALL FAIL: ${NLOCK} of the 7 checks failed."
    if [ "${V_PFD}" = "FAIL" ]; then
      # The integration guard invalidates every other row, so it is read first.
      s="${s} Check 7 -- the INTEGRATION guard, not a lock criterion -- is among"
      s="${s} the failures, and it has to be read first: the PFD's DN branch does"
      s="${s} not assert in the late window at all (${DN_LVL} V mean). In a locked"
      s="${s} loop both branches pulse once per reference cycle for the"
      s="${s} reset-delay overlap, so a silent DN branch is the signature of a"
      s="${s} transient stepping clean over the PFD's 0.33-0.39 ns internal set"
      s="${s} pulse: the detector was never resolved by the integration. Until"
      s="${s} that is fixed (the ${KTMAX} ceiling, see Simulator settings above)"
      s="${s} NOT ONE of checks 1-6 may be read as a statement about the design."
      s="${s} They are reading an artefact of the solver, and this record"
      s="${s} substantiates nothing until it is re-run."
    elif [ "${V_N}" = "FAIL" ]; then
      s="${s} The divide ratio itself is wrong -- f_out/f_fb measured ${NMEAS}"
      s="${s} against N = ${KN} -- so the feedback path is not dividing by the"
      s="${s} ratio the configuration asked for. That is an assembly or"
      s="${s} divider-encoding fault, and it is upstream of everything else here:"
      s="${s} checks 1, 2, 4 and 5 are all measured against an N*f_ref target the"
      s="${s} loop was never actually driving toward, so they are not independent"
      s="${s} results and must not be read as loop-dynamics evidence."
    else
      s="${s} The two guards both PASS, so this is not a wiring result and not"
      s="${s} an integration result: the divide ratio is ${NMEAS} against"
      s="${s} N = ${KN}, so the loop closed through the configured divider, and"
      s="${s} the PFD's DN branch asserts at ${DN_LVL} V mean, so the timestep"
      s="${s} resolved the detector."
      if [ "${V_VCTRL}" = "FAIL" ]; then
        s="${s} The control node, however, left DR-001 Decision 2's usable"
        s="${s} ${ACC_VCTRL_LO}-${ACC_VCTRL_HI} V window (${VC_MIN} .."
        s="${s} ${VC_MAX} V), so whatever the phase and frequency rows say, this"
        s="${s} is not a lock this record may claim -- it would be one held off"
        s="${s} the end of the V->I converter's characterised range."
      fi
      if [ "${V_FERR}" = "FAIL" ] || [ "${V_PHI}" = "FAIL" ] \
         || [ "${V_FOUT}" = "FAIL" ] || [ "${V_LOCK}" = "FAIL" ]; then
        s="${s} What failed is the lock criterion itself, and ${trend}."
        case "${trend}" in
          *SHRINKING*)
            s="${s} A phase error still closing at ${KTB} is a MEASUREMENT-WINDOW"
            s="${s} result, not a design one. The two honest resolutions are a"
            s="${s} longer transient with the window re-placed where the loop's"
            s="${s} own dominant pole says lock lands, or -- if that lands beyond"
            s="${s} \`spec/pll.md\`'s lock-time target -- a filter change carried"
            s="${s} through a \`spec/\` decision record. Moving the window just far"
            s="${s} enough to flip these verdicts is neither." ;;
          *GREW*)
            s="${s} A phase error that GROWS between the two instants is not a"
            s="${s} window problem and no amount of extra transient will fix it:"
            s="${s} the loop is not converging at this operating point, and that"
            s="${s} has to be run down as a design or configuration result before"
            s="${s} any measurement instant is touched." ;;
          *FLAT*)
            s="${s} A flat phase error means the loop HAS settled, and settled"
            s="${s} outside the criterion: this is a static-accuracy result, not"
            s="${s} a convergence one, and a longer transient will not move it." ;;
        esac
      fi
    fi
  fi

  # The scope sentence is unconditional on purpose: the reading most likely to
  # be over-cited is the PASS one.
  if [ "${VERDICT}" = "PASS" ]; then
    s="${s} That is the whole of what it establishes:"
  else
    s="${s} Either way this stays"
  fi
  s="${s} one corner, one N, one band -- the acceptance"
  s="${s} gate for #52's top-level assembly and nothing more. It must not be"
  s="${s} quoted for lock time, jitter, spurs, power or band coverage over PVT;"
  s="${s} those are #12's, #13's and #14's campaigns, each over the full grid"
  s="${s} against this same assembled DUT."

  printf '%s\n' "${s}" | wrap_para
}

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
  PFD duty   UP / DN      ${UP_LVL} / ${DN_LVL} V mean              ${V_PFD}
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
  real frequency error? This is the acceptance gate for the top-level assembly landing
  in \`design/\`, and nothing more: it is one corner, one N, one band. It does
  **not** substantiate any spec line, and it is not a substitute for #12
  (\`lock-time\`, \`output-range\`), #13 (\`period-jitter\`) or #14
  (\`supply-sensitivity\`), each of which owns a PVT campaign against this same
  assembled DUT.
- **Netlist provenance**: schematic (\`design/pll_top.sch\`, exported by
  \`design/netlist.sh\` to \`design/netlist/pll_top.spice\`) ->
  \`sim/pll-top-smoke/netlist-snapshots/${RID}.spice\` (exported subcircuit +
  testbench, concatenated by \`sim/lib/pll_top_dut.sh\`), SHA-256
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
    \`sim/lib/pll_top_dut.sh\`, the single path from \`design/pll_top.sch\`
    to a runnable deck (\`sim/supply-sensitivity\` (#14) uses the same helper;
    #12's \`lock-time\` and \`output-range\` still assemble a closed loop from
    the individual block exports instead, and converging them is follow-up
    work -- see \`sim/README.md\`). The DUT is not
    hand-transcribed anywhere: a schematic edit this deck does not track is a
    netlist error, not a divergent second copy of the design.
  - **Starting condition, and what it deliberately excludes**:
    \`.ic v(vctrl) = ${KVSTART}\`. Band ${KBAND} runs at 60.7 MHz there
    (\`sim/vco-tuning-range\` record 20260731-175947-0a12e6c,
    \`kvco_by_point.csv\`, row \`typical,27,3.30\`), i.e. 16 % below the
    ${KN} x ${KFREF} Hz target, so the loop starts with a real frequency error
    and the PFD has to frequency-detect its way in rather than settle a phase.
    It is **not** released at 0 V, for two reasons that both matter to what
    this record may be cited for. Below the band floor the VCO is outside the
    range \`sim/vco-tuning-range\` characterised at all, so a 0 V release would
    spend its first and longest phase in territory no record covers; and the
    control node slews at Icp/C1 = 5 uA / 120.8 pF = 41 mV/us, i.e. 24 us per
    volt, so the release point sets the run length almost by itself. **This
    record therefore says nothing about cold-start lock time** -- that is #12's
    \`lock-time\` campaign, over the full PVT grid, and the number here would
    be an underestimate of it. The VCO ring's DC symmetry is broken with the
    same \`.ic\` pattern \`sim/vco-tuning-range\` uses; \`uic\` is deliberately
    not used, so the constant-gm bias generator is solved to its operating
    point before t = 0 and the run is loop acquisition rather than bias
    start-up.
  - **Lock criterion**, stated before the run and applied to it:
    1. **Frequency** -- the residual fractional frequency error, measured as
       the DRIFT of the REF->FB phase between t = ${KTA} and t = ${KTB},
       must be <= ${ACC_FERR}. In a type-II loop a residual frequency error
       makes the static phase slip linearly at exactly (df/f) seconds per
       second, so differencing one phase measurement against another 3 us
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
    7. **The PFD's DN branch asserts at all** -- mean DN level over the late
       window >= ${ACC_DN_FRAC} of the rail. This is not a lock criterion; it
       is the guard described under Simulator settings below, and it is gated
       separately so that "the loop did not lock" and "the integration did not
       resolve the detector" cannot be confused for one another.
    Both phase instants are placed on a reference half-period, so "the first
    REF rise after t" and "the first FB rise after t" are the same cycle's
    pair and the measurement cannot alias by a whole reference period.
  - **Where the measurement window sits, and why it sits there.** The window
    is at ${KTA} / ${KTB} in a ${KTSTOP} transient, and it is placed from this
    repo's own ratified numbers rather than from where the verdicts turn.
    \`spec/pll.md\`'s Lock time section states a **structural settling floor
    of ~43 us**, "regardless of how much Icp is applied", because the dominant
    closed-loop pole sits near \`1/(2*pi*R*C1)\` = 17.09 kHz -- a 9.31 us time
    constant, and a property of DR-001 Decision 1's fixed filter rather than
    of the drive level. DR-006 Decision 7 is where that was measured, and it
    is why the < 20 us stretch target was **removed** from the ratified spec
    rather than carried. Any window earlier than ~43 us is therefore asking
    this loop for something the spec already says it cannot do; the first
    record of this campaign (\`20260801-085349-0e5c22d\`, superseded) measured
    at 14/17 us in a 20 us transient and read FAIL for exactly that reason,
    with its phase error visibly still closing (19.57 ns -> 14.05 ns) at
    \`tstop\`.
    The window is then placed against the **tightest** of the seven criteria,
    which is not check 2's ${ACC_PHI_FRAC} of a reference period
    (= 2.22 ns at ${KFREF} Hz) but the block's own LOCK flag:
    \`sim/lock-detector\` record \`20260731-095213-0bffe91\` measures its
    comparator window at this corner (\`typical\`/27 C/3.30 V) as asserting up
    to 1.2 ns and not asserting from 1.5 ns, and \`spec/pll.md\`'s ratified
    1 ns phase bound is set from that same measured window (0.877 ..
    1.702 ns over the corners it swept) precisely so the criterion and the
    on-chip observable describe one event rather than two.
    Extrapolating the superseded record's own measured decay
    (14.05 ns at 17 us, tau = 9.05 us, against the 9.31 us \`R*C1\` predicts)
    puts the phase error near 0.4 ns at ${KTA} -- roughly 3x inside that
    tightest criterion, and about 0.75 time constants past the ratified
    floor. It is not placed later still because the phase error does not
    decay to zero: the charge pump's own static offset (-0.06 .. +0.67 ns
    over 45 corners, \`design/README.md\`'s up/down mismatch budget, term 4)
    is the asymptote, and it already sits inside the detector's window.
  - **Simulator settings**: \`.tran ${KTSTEP} ${KTSTOP} 0 ${KTMAX}\`,
    \`reltol 1e-3\`, \`abstol 1e-13\`, \`vntol 1e-6\`, \`rshunt 1e12\`,
    \`itl4 200\`.
  - **The ${KTMAX} timestep ceiling is set by the PFD's INTERNAL SET PULSE,
    and getting this wrong produces a false negative rather than a noisy
    one.** \`design/edgedet.sch\` fires each of the PFD's two SR latches from
    AND(X, NOT(X delayed by 5 inverters)); that pulse measures 0.33-0.39 ns at
    this corner. The UP/DN pulse it eventually produces is 1.1-1.9 ns wide (the
    24-inverter reset chain), and sizing the ceiling from THAT number -- the
    obvious reading, since UP/DN carry the loop gain -- is the trap: a 500 ps
    ceiling yields a mean internal step of 0.38 ns, so ngspice steps clean over
    the set pulse on roughly half the feedback edges. Each miss is a feedback
    edge the PFD never sees, and the loop then reads as jammed with UP asserted,
    ramping Vctrl to the rail while the feedback is ALREADY faster than the
    reference. That is a "the loop does not lock" result which is entirely an
    artefact of the integration, and it is why check 7 exists. Every
    closed-loop campaign inherits this bound; it is a property of the PFD, not
    of this testbench.
  - \`rshunt\` and \`itl4\` carry over from \`sim/pfd-deadzone\` for the same
    reasons documented there (floating cascode mid-nodes on the disabled trim
    legs; the dump-node buffer's two MOS gates on the control node).
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
  | 7 | PFD DN branch asserts (integration guard, not a lock criterion) | mean DN >= ${ACC_DN_FRAC} of the rail | ${DN_LVL} V | **${V_PFD}** |

  Supporting numbers (reported, not gated):

  | Quantity | Value |
  |---|---|
  | Vctrl at release (\`.ic\`, ${KVSTART} V) | ${VC_INI} V |
  | Vctrl settled, late-window average | ${VC_AVG} V |
  | Vctrl peak-to-peak ripple, late window | ${VC_RIPPLE} V |
  | LOCK flag first asserts at | ${T_LOCK} s |
  | PFD UP / DN mean level, late window | ${UP_LVL} V / ${DN_LVL} V |
  | phase error at ${KTA} / at ${KTB} | ${PHI_A} s / ${PHI_B} s |
  | feedback frequency f_fb | ${FFB} Hz |
  | supply current, ref / vco / div domain | ${I_REF} / ${I_VCO} / ${I_DIV} A |
  | total power at this corner | ${P_TOT_MW} mW |

  **Overall: ${VERDICT}** (${NLOCK} of 7 checks failed).

$(record_conclusion)

  The Vctrl ripple and the supply/power figures are here because a loop that
  "locks" while drawing an implausible current, or while the control node
  swings across its whole window every reference cycle, is not actually
  working -- not because this record substantiates a ripple, spur or power
  claim. It does not; #14 does.
- **Links**:
  - Testbench: \`sim/pll-top-smoke/testbench/tb_pll_smoke.sp\`
  - Assembly: \`sim/lib/pll_top_dut.sh\`
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
