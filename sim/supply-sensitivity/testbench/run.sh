#!/usr/bin/env bash
# gf180-pll :: supply-sensitivity :: closed-loop supply sensitivity and power
#
# The campaign sim/README.md reserves for #14: what the WHOLE PLL does across
# the ratified 3.3 V +/- 10 % supply range, and what it costs in power while it
# does it.  Four things, each with its own testbench run and its own criterion:
#
#   1. output frequency vs. supply, over the full 45-point PVT grid, reported
#      as the deviation from the same corner's nominal-supply value;
#   2. static phase offset vs. supply, over the same grid, measured two
#      independent ways (REF->FB skew, and the UP/DN pulse-WIDTH difference
#      that produces it) against the POST-#24 charge pump;
#   3. does the loop stay locked through a supply STEP and a supply RAMP, and
#      how much disturbance couples through from the VCO supply pushing #8
#      already measured open-loop;
#   4. quiescent and dynamic supply current with the loop locked at 100 MHz,
#      broken down per supply domain, against the draft < 5 mW target.
#
# DR-002 Decision 3 ratifies 3.3 V thick-oxide only for v1, so the 2.97 /
# 3.30 / 3.63 V axis of the default corner grid IS the complete supply-axis
# requirement -- there is no separate 1.8 V or 5 V supply-flavour sweep to run.
#
# The DUT is design/pll_top.sch (#52), assembled by
# sim/lib/pll_top_dut.sh (#52's helper, renamed -- see its header).  This
# campaign does not build a top level of
# its own; nothing here is a hand-transcribed copy of the design.
#
# Usage:
#   ./run.sh                 # run everything and mint a record
#   ./run.sh --check         # one nominal point, print metrics, write NO record
#   ./run.sh --op-table      # print the derived operating-point table and exit
#   SIM_FORCE=1 ./run.sh     # ignore cached runs in work/ and re-simulate
#   SIM_JOBS=8 ./run.sh      # override the parallel job count
#
#   SIM_TSTOP / SIM_TA / SIM_TB
#                            override the steady-state transient length and its
#                            two late measurement instants, so a corner that is
#                            still converging can be re-run longer instead of
#                            being reported as a design result.
#   SIM_EXTEND=off           disable the automatic settling escalation (below);
#   SIM_EXTEND_TSTOP/_TA/_TB the length it escalates to;
#   SIM_EXTEND_MAX=<n>       cap how many corners it escalates.
#   SIM_TMAX                 run at a timestep ceiling other than the shared
#                            closed-loop bound.  Its one sanctioned use
#                            (sim/lib/simenv.sh) is a bound-sensitivity study;
#                            such a run gets its own work directory and carries
#                            its ceiling in every row it emits, so it cannot be
#                            mistaken for a compliant one.
#   SIM_FINE=off             disable the timestep-ceiling cross-check that
#                            follows the escalation.  The cross-check is a no-op
#                            unless SIM_TMAX put the grid off the bound; when it
#                            did, it is what distinguishes a genuinely
#                            under-damped corner from an under-RESOLVED one.
#   SIM_FINE_TMAX / SIM_FINE_MAX  the ceiling it re-runs at (default: the
#                            bound), and a cap on how many corners it reaches.
#
#   SIM_SUPERSEDES=<record-id> SIM_SUPERSEDES_NOTE='<why>' ./run.sh
#                            mint with a **Supersedes** field (sim/README.md ::
#                            "Status / supersession language").
#   SIM_SUPERSEDES_PR='PR #62'
#                            the pull request that landed the superseded
#                            record, named in the new record's supersession
#                            prose.  A record can read the superseded record's
#                            commit and timestamp out of the file itself; the
#                            PR that merged it is the one fact it cannot, so it
#                            is passed in rather than guessed.
#
# Every run is resumable: a completed run is reused only on an exact match of
# the deck mtime AND the full parameter list, never on the deck alone.

# SC2034 ("appears unused") is disabled for this file: the KTAU / ACC_* / CITE_*
# constants below are consumed by report.sh, which re-reads this file's
# assignment block by hand (see its header) so that the criterion the record
# STATES and the criterion the runner APPLIES cannot drift apart.  They are
# deliberately not exported -- report.sh must read what this file declares, not
# whatever happens to be in the environment.
# shellcheck disable=SC2034
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP="$(cd "${HERE}/.." && pwd)"
ROOT="$(cd "${EXP}/../.." && pwd)"
# shellcheck source=../../lib/simenv.sh
. "${ROOT}/sim/lib/simenv.sh"
# shellcheck source=../../lib/pll_top_dut.sh
. "${ROOT}/sim/lib/pll_top_dut.sh"

WORK="${EXP}/work"
DUT_LOCK="${WORK}/dut_lock.sp"
DUT_DYN="${WORK}/dut_dyn.sp"

# ---------------------------------------------------------------------------
# The operating point, and where every number comes from.
# ---------------------------------------------------------------------------
# KFOUT   100 MHz output -- the frequency #14's power criterion names, and
#         inside DR-002 Decision 2's ratified 10-200 MHz v1 band.
# KN      N = 8, mid of the ratified 4-64 range (DR-001 Decision 3).
# KFREF   12.5 MHz reference (= 100 MHz / 8), inside DR-002 Decision 1's
#         ratified 1-25 MHz range.
# KTRIM   Icp trim code 2 (three unit legs), the nominal setting
#         design/README.md characterises the charge pump at, and the setting
#         sim/loop-dynamics shows meeting both the 45 deg phase-margin
#         criterion and the f_c < f_ref/10 ceiling across the 8-16 MHz
#         reference decade this operating point sits in.
KFOUT=100e6
KN=8
KFREF=12.5e6
KTRIM=2

# The SECOND frequency point, used only for the quiescent/dynamic power split
# (see "Quiescent vs. dynamic" below).  Same N, half the reference, so f_ref
# and f_out scale together and a two-point fit in f_out is unambiguous.
KFOUT2=50e6
KFREF2=6.25e6

# Transient controls, shared by every steady-state run.
# KTMAX   The ceiling on the ngspice INTERNAL timestep is NOT this campaign's to
#         choose: it is a property of the PFD every closed-loop deck in this repo
#         inherits, and it lives in one place -- `SIMENV_CLOSED_LOOP_TMAX` in
#         `sim/lib/simenv.sh`, documented in `sim/README.md`.  The bound is set
#         by `design/edgedet.sch`'s INTERNAL set pulse (0.33-0.39 ns), not by the
#         1.1-1.9 ns UP/DN OUTPUT pulse this campaign used to derive it from and
#         not by f_out; an integrator whose step is comparable to the set pulse
#         steps clean over it on a large fraction of feedback edges and the loop
#         reads as jammed with UP asserted -- a false "does not lock", not a
#         noisy one (#52/PR #64 measured it, #65/PR #75 hoisted it).
#         This campaign's previous 400 ps and its "set by the CHARGE PUMP"
#         rationale were reasoning from the output pulse, i.e. from the wrong
#         pulse, and are replaced here by the shared constant rather than by a
#         second derivation of it.  **The 9-corner record this campaign already
#         has on `main` (20260801-024935-c4fe724) was taken at 400 ps and is
#         therefore qualified by that bound**; re-examining it is #69's scope,
#         and nothing here edits it.
# KTSTOP  12 us.  Short because the warm start in tb_supply_lock.sp
#         pre-charges BOTH loop-filter nodes -- the control node AND the
#         series capacitor C1 that actually holds the loop's state -- so the
#         run does not contain an acquisition ramp.  (Pre-charging only VCTRL
#         costs 122 pF x V_lock / Icp = tens of microseconds of pure ramp at
#         every corner; that is a real trap and the deck documents it.)  What
#         is left is the residual settling of the loop's slowest pole,
#         1/(2*pi*R*C1) = 17.1 kHz => tau = 9.3 us, from whatever error the
#         predicted lock point carries.  KTA at 6.4 us and KTB at 9.6 us are
#         0.69 tau and 1.03 tau, so this record is NOT entitled to assume the
#         residual away: `ferr` measures it directly and the lock criterion is
#         applied to the measured value at every corner.  The run has 2.4 us
#         left after KTB for the frequency measurements (100 CLK cycles = 1 us
#         at 100 MHz, 2 us at 50 MHz; 10 FB cycles = 0.8 us / 1.6 us).
# KTA/KTB Both are whole multiples of 160 ns, which places them on a reference
#         HALF-period for BOTH reference frequencies (12.5 MHz: tstart = 40 ns;
#         6.25 MHz: tstart = 80 ns), so "the first REF rise after t" and "the
#         first FB rise after t" are the same cycle's pair at either setting.
#
# KTSTOP/KTA/KTB are OVERRIDABLE (`SIM_TSTOP`/`SIM_TA`/`SIM_TB`) because a
# corner reported as still converging has to be re-runnable at a longer
# transient instead of being reported as a design result.  KTSTOP_BASE is the
# unoverridden default, kept separately for two reasons: a run at a
# non-default length gets its OWN work directory (so the long run does not
# destroy the default-length run it is being compared against), and every
# emitted summary row carries the length it was actually run at, so the
# record's `tstop` column is per-row truth rather than a script constant.
KTSTOP_BASE=12.0u
KTSTOP="${SIM_TSTOP:-${KTSTOP_BASE}}"
KTSTEP=20n
# KTMAX_BASE is the shared closed-loop BOUND; KTMAX is what THIS invocation
# actually runs at.  They differ only under `SIM_TMAX`, whose one sanctioned use
# (`sim/lib/simenv.sh`) is a deliberate bound-sensitivity study -- and they have
# to stay distinguishable, because a run at a non-bound ceiling gets its own
# work directory and carries its ceiling in every summary row it emits, so that
# such a run can never be quietly mistaken for a compliant one.
#
# The literal is restated here rather than derived, because `simenv.sh` folds
# the SIM_TMAX override into `SIMENV_CLOSED_LOOP_TMAX` itself and there is then
# no expression left that yields the unoverridden bound.  The guard below makes
# the duplication safe: if the shared constant moves and this one does not, the
# campaign refuses to run rather than minting a record against a stale bound.
KTMAX_BASE=100p
KTMAX="${SIMENV_CLOSED_LOOP_TMAX}"
if [ -z "${SIM_TMAX:-}" ] && [ "${KTMAX}" != "${KTMAX_BASE}" ]; then
  echo "ERROR: KTMAX_BASE (${KTMAX_BASE}) has drifted from sim/lib/simenv.sh's" >&2
  echo "       SIMENV_CLOSED_LOOP_TMAX (${KTMAX}).  Update this runner to the" >&2
  echo "       shared bound; do not mint a record against a stale one." >&2
  exit 1
fi
# The ceiling the cross-check re-runs at is the BOUND itself: the cross-check
# exists for the case where the grid was deliberately run coarser than the
# bound, and its job is to say whether that choice, rather than the loop, is
# what produced a lock-criterion failure.  When the grid already ran AT the
# bound the two are equal and the stage is a no-op, which is the normal case.
KTMAX_X="${SIM_FINE_TMAX:-${KTMAX_BASE}}"
KTA="${SIM_TA:-6.4u}"
KTB="${SIM_TB:-9.6u}"

# The settling escalation (see "Settling escalation" in Main).  A corner whose
# measured residual frequency error exceeds ACC_FERR at KTSTOP has NOT been
# shown to be a design failure -- it has been shown to be unsettled -- so the
# runner re-runs it automatically at KTSTOP_X and the record reports the pair.
# 36.8u is 3.96 KTAU with the late window at 3.35/3.70 KTAU, against
# 0.69/1.03 KTAU at the default length: an exponentially-settling loop drops
# its residual by e^-2.7 (~x0.07) between the two, and one that does not is
# not merely slow.  Both instants stay whole multiples of 160 ns, so they
# remain on a reference half-period for both reference frequencies.
KTSTOP_X="${SIM_EXTEND_TSTOP:-36.8u}"
KTA_X="${SIM_EXTEND_TA:-31.2u}"
KTB_X="${SIM_EXTEND_TB:-34.4u}"
# The loop's own settling time constant, 1/(2*pi*R*C1) = 17.1 kHz => 9.3 us,
# derived above.  Named here so report.sh states one number everywhere it
# compares a rate or a window against "the loop", rather than restating it.
KTAU=9.3u

# Supply step/ramp profile (criterion 3).  One transient carries both events.
# Both rates are stated against the loop's own settling time constant KTAU
# (9.3 us, see above) because that is the only timescale the loop has, and
# because #14's acceptance criterion requires the record to name the rates.
# KD_STEP  a 3.30 -> 3.63 V step with a 100 ns edge.  100 ns is KTAU/93, and
#          ~1/18 of the 1.76 us period of the nominal closed-loop crossover
#          (f_c ~ f_ref/22 = 570 kHz), so it is a step as far as the loop is
#          concerned, while staying slow enough that the rail is not a delta
#          function the integrator cannot resolve.
# KD_RAMP  3.63 -> 2.97 V over 6.4 us (16.0u..22.4u), i.e. 103 mV/us.  That is
#          0.69 KTAU -- 64x slower than the step edge, but still FASTER than
#          the loop's own settling, so it is NOT a quasi-static tracking test:
#          it moves the rail on the same timescale the loop responds on, which
#          is where a loop with no margin visibly lags.  The two events
#          therefore probe rejection at two rates a factor of 64 apart, one far
#          above the loop's response and one just above it; a true tracking
#          test needs a ramp of several KTAU and is NOT part of this profile.
#          (Do not "fix" this by editing the constants below without re-running:
#          the frozen -dyn.spice snapshot and every recorded number are taken
#          at the values coded here.)
KD_LO=3.30
KD_HI=3.63
KD_END=2.97
KD_TSTEP=5.6u
KD_TEDGE=100n
KD_TRAMP=16.0u
KD_TREND=22.4u
KD_TSTOP=30.4u
KD_DECIM=20e-9

# In-loop control-voltage calibration (the `rforce` pre-pass).  Two forced
# points per corner, KVPRE_D apart, straddling #8's standalone-VCO prediction;
# the runner then solves the measured in-loop f(Vctrl) line for the control
# voltage that gives the target output frequency.  A short transient suffices:
# with VCTRL held by an ideal source there is no loop to settle, only the VCO's
# own bias generator, and KVPRE_TB is 4 reference periods in.
#
# The length of that transient is NOT a free constant.  tb_supply_lock.sp
# measures f_out over a fixed COUNT of output cycles (100 of them, because
# ngspice's `.meas ... rise=` index is not an expression context) starting at
# `tb`, so the run time a calibration point needs scales as 1/f_out -- and the
# deck says so in as many words, asking the runner for "at least 2.4 us of run
# after tb".  KVPRE_TSTOP below states that length for KFOUT and KFOUT only.
# Used unscaled at the HALF-frequency point of the power split it is not merely
# tight, it is impossible: 100 cycles at KFOUT2 need 2.0 us and the window is
# 1.12 us, so `fout` measures `failed`, the solve returns nan, and every split
# corner is silently dropped -- which is exactly why the campaign that
# introduced the split reported it as NOT MEASURED.  Hence vpre_tstop_for().
KVPRE_D=0.25
KVPRE_TSTOP=1.44u
KVPRE_TA=0.16u
KVPRE_TB=0.32u
KVPRE_RON=1m
KVPRE_ROFF=1e15
# The retry window, as a multiple of the 100 output cycles the deck counts.
# 2.4 is the headroom tb_supply_lock.sp asks for, against the 1.12 the nominal
# window carries; a point whose f_out could not be measured in the nominal
# window is re-run here rather than being reported as nan.  Same principle as
# the settling escalation below: a measurement that did not fit its window is
# re-measured in a bigger one, not recorded as a result.
KVPRE_RETRY_K=2.4

# vpre_tstop_for <f_out> -- the calibration transient for a target frequency.
# At KFOUT it returns KVPRE_TSTOP verbatim (same string, so a run cached at the
# documented length stays cached); elsewhere it scales the post-tb part of that
# window by KFOUT/f_out, which holds the cycle-count margin CONSTANT rather
# than holding the seconds constant.
vpre_tstop_for() {
  if [ "$1" = "${KFOUT}" ]; then printf '%s' "${KVPRE_TSTOP}"; return; fi
  awk -v ts="${KVPRE_TSTOP%u}" -v tb="${KVPRE_TB%u}" -v f0="${KFOUT}" -v f="$1" \
    'BEGIN{ printf "%.6gu", tb + (ts - tb) * f0 / f }'
}
# vpre_tstop_retry_for <f_out> -- the longer window a failed point is re-run at.
vpre_tstop_retry_for() {
  awk -v tb="${KVPRE_TB%u}" -v k="${KVPRE_RETRY_K}" -v f="$1" \
    'BEGIN{ printf "%.6gu", tb + k * 100 / f * 1e6 }'
}
# Where the solved control voltage is allowed to land.  Outside this the
# solution is not a control voltage, it is an extrapolation off the end of the
# measured line, and the runner says so rather than simulating it.
KVPRE_LO=0.40
KVPRE_HI=2.95

# Acceptance thresholds.  Stated here, before the run, not discovered from it.
ACC_FERR=1e-3          # |residual fractional frequency error| in lock
ACC_PHI_FRAC=0.02      # |static phase error| as a fraction of a reference period
ACC_NTOL=0.01          # |f_out/f_fb - N|
ACC_LOCK_FRAC=0.90     # LOCK flag level in the late window, fraction of the rail
ACC_VCTRL_LO=0.9       # DR-001 Decision 2's usable control window
ACC_VCTRL_HI=2.4
ACC_PWR_MW=5.0         # draft power target (placeholder pending #1)
ACC_FDEV_PPM=1000      # |f_out(vdd) - f_out(3.30 V)| / f_out(3.30 V), ppm

# #8's open-loop VCO supply-pushing figures, CITED not re-derived (#14's
# acceptance criterion says so in as many words).  Source:
# sim/vco-tuning-range/records/20260731-184845-0a12e6c.md, sections 1 and 2.
CITE_VCO_RECORD=20260731-184845-0a12e6c
CITE_PUSH_WORST=-50.7          # %/V, static, ss/-40C band 4
CITE_PUSH_MEDIAN=-39.4         # %/V, static, median over the grid
CITE_STEP_WORST=-47.7          # MHz/V, transient, 0.1 V step, band 5 ~100 MHz

# #8's measured f(Vctrl) table -- the source of both the band code and the
# warm-start control voltage for every corner below.  Using the committed
# evidence rather than a fresh sweep is the point: the operating point this
# campaign runs at is derived from a citable record, and a reader can check the
# derivation without re-simulating anything.
VCO_TUNING="${ROOT}/sim/vco-tuning-range/corners/20260731-175947-0a12e6c/vco_tuning.csv"

# Passive sections.  Named explicitly rather than defaulted: sim/README.md
# warns that a MOS-only sweep silently pins the passives at typical, and this
# DUT contains the loop filter whose R and C set the loop bandwidth.  Here they
# ARE all typical -- the point is that the record says so because the run put
# them there.  The justification for not sweeping them is in the record.
PASSIVES="res_typical,moscap_typical,mimcap_typical"

libs_for() { echo "$1,${PASSIVES}"; }

# The corner axes.  Default is the full 45-point grid sim/README.md prescribes.
# SIM_BUNDLES / SIM_TEMPS narrow it for a compute-limited run; whatever is
# actually swept is what report.sh writes into the record's corner-matrix
# field, derived from the collected rows rather than from these defaults, so a
# reduced run can never describe itself as a full one.
GRID_BUNDLES="${SIM_BUNDLES:-typical ff ss fs sf}"
GRID_TEMPS="${SIM_TEMPS:--40 27 125}"
# The corners the step/ramp deck runs at, and the corners the second frequency
# point of the power split runs at.  Both are subsets by design (see the
# record's Methodology), and both are overridable for the same reason.
DYN_PICKS="${SIM_DYN_PICKS:-typical 27}"
SPLIT_BUNDLES="${SIM_SPLIT_BUNDLES:-typical}"
SPLIT_TEMPS="${SIM_SPLIT_TEMPS:-27}"

in_list() { case " $2 " in *" $1 "*) return 0 ;; *) return 1 ;; esac }

# ---------------------------------------------------------------------------
# Operating-point derivation
# ---------------------------------------------------------------------------
# For each (bundle, temperature) pick ONE band code -- band select is a static
# input with no calibration FSM (DR-001 Decision 2), so it cannot be re-chosen
# when the supply moves, and picking it per supply would measure a different
# configuration at each supply point and call the difference "supply
# sensitivity".  The chosen code is the one that reaches the target frequency
# at ALL THREE supplies with the control voltage as close to mid-window as
# possible; the per-supply control voltage it implies is the warm start.
#
# Prints: bundle,temp_c,band,vctrl_2.97,vctrl_3.30,vctrl_3.63
# A (bundle, temperature) row for which NO band reaches the target at all three
# supplies inside the search window is printed with band = -1, and the caller
# treats that as a campaign-level finding rather than papering over it.
derive_op_points() {
  local target="$1" lo="${2:-0.85}" hi="${3:-2.70}"
  awk -F, -v target="${target}" -v LO="${lo}" -v HI="${hi}" '
    !/^#/ && $1 != "bundle" {
      b=$1; t=$2; v=$3; bd=$4; vc=$5; f=$6;
      if (b == "all-slow" || b == "all-fast") next;   # composite bundles are
                                                      # not on the 45-point grid
      k = b "|" t "|" v "|" bd; n[k]++; VC[k,n[k]]=vc; F[k,n[k]]=f;
    }
    END {
      # Vctrl at the target frequency, by linear interpolation inside the one
      # bracketing interval of the measured f(Vctrl) curve.  No extrapolation:
      # a curve that does not bracket the target simply has no entry.
      for (k in n) {
        for (i = 1; i < n[k]; i++) {
          f1 = F[k,i]; f2 = F[k,i+1];
          if ((f1 - target) * (f2 - target) <= 0 && f1 != f2)
            V[k] = VC[k,i] + (target - f1) * (VC[k,i+1] - VC[k,i]) / (f2 - f1);
        }
      }
      nb = split("typical ff ss fs sf", BU, " ");
      nt = split("-40 27 125", TE, " ");
      ns = split("2.97 3.30 3.63", SU, " ");
      mid = 0.5 * (LO + HI);
      for (bi = 1; bi <= nb; bi++) for (ti = 1; ti <= nt; ti++) {
        bestband = -1; bestcost = 1e9; bestline = ",,,";
        for (bd = 0; bd <= 7; bd++) {
          ok = 1; cost = 0; line = "";
          for (si = 1; si <= ns; si++) {
            kk = BU[bi] "|" TE[ti] "|" SU[si] "|" bd;
            if (!(kk in V)) { ok = 0; break }
            vv = V[kk];
            if (vv < LO || vv > HI) { ok = 0; break }
            d = vv - mid; if (d < 0) d = -d;
            if (d > cost) cost = d;
            line = line sprintf(",%.4f", vv);
          }
          if (ok && cost < bestcost) { bestcost = cost; bestband = bd; bestline = line }
        }
        printf "%s,%s,%d%s\n", BU[bi], TE[ti], bestband, bestline;
      }
    }' "${VCO_TUNING}"
}

# ---------------------------------------------------------------------------
# One steady-state run.
#   --one-lock <bundle> <temp> <vdd> <band> <vctrl0> <fout> <fref> <sumfile>
# ---------------------------------------------------------------------------
if [ "${1:-}" = "--one-lock" ]; then
  shift
  bundle="$1"; temp="$2"; vdd="$3"; band="$4"; vc0="$5"; fout="$6"; fref="$7"; sum="$8"
  kind="f$(awk -v f="${fout}" 'BEGIN{printf "%03d", f/1e6}')"
  tag="${kind}_${bundle}_T${temp}_V${vdd}"
  # A non-default transient length, or a non-default timestep ceiling, gets its
  # own work directory -- so a settling re-run or a timestep-ceiling cross-check
  # ADDS evidence rather than overwriting the run it is compared with.
  [ "${KTSTOP}" = "${KTSTOP_BASE}" ] || tag="${tag}_X${KTSTOP}"
  [ "${KTMAX}" = "${KTMAX_BASE}" ]   || tag="${tag}_M${KTMAX}"
  tag=$(simenv_mktag "${tag}")
  rundir="${WORK}/${tag}"; log="${rundir}/ngspice.log"
  libs="$(libs_for "${bundle}")"

  params=( "vsup=${vdd}" "fref=${fref}" "nratio=${KN}" "vctrl0=${vc0}"
           "rforce=${KVPRE_ROFF}"
           "tstop=${KTSTOP}" "tstep=${KTSTEP}" "tmax=${KTMAX}"
           "ta=${KTA}" "tb=${KTB}" )
  # shellcheck disable=SC2207
  params+=( $(cloop_band_params "${band}") )
  # shellcheck disable=SC2207
  params+=( $(cloop_trim_params "${KTRIM}") )
  # shellcheck disable=SC2207
  params+=( $(cloop_divider_params "${KN}") )
  sig="${libs}|${temp}|${params[*]}"

  if [ -z "${SIM_FORCE:-}" ] && [ -f "${log}" ] && [ "${log}" -nt "${DUT_LOCK}" ] \
     && [ "$(cat "${rundir}/.sig" 2>/dev/null)" = "${sig}" ] \
     && grep -q "Total analysis time" "${log}" 2>/dev/null; then
    :
  else
    simenv_run_deck "${DUT_LOCK}" "${WORK}" "${tag}" "${libs}" "${temp}" "${params[@]}" \
      >/dev/null 2>&1 || true
    grep -q "Total analysis time" "${log}" 2>/dev/null || {
      echo "ERROR: ngspice did not complete ${tag} (see ${log})" >&2; exit 1; }
    printf '%s' "${sig}" >"${rundir}/.sig"
  fi

  m() { simenv_meas "${log}" "$1"; }
  # 28 fields.  The last two are the transient length and the timestep ceiling
  # this row was actually run at -- per-row truth, because after the escalation
  # and the cross-check below they are no longer one constant for the grid.
  printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n' \
    "${bundle}" "${temp}" "${vdd}" "${fout}" "${band}" "${KTRIM}" "${fref}" "${KN}" "${vc0}" \
    "$(m fout)" "$(m ffb)" "$(m nmeas)" "$(m ferr)" "$(m phi_b)" \
    "$(m skew1)" "$(m skew2)" "$(m skew3)" "$(m wup1)" "$(m wdn1)" \
    "$(m vctrl_avg)" "$(m vctrl_min)" "$(m vctrl_max)" "$(m lock_lvl)" \
    "$(m i_core)" "$(m i_vco)" "$(m i_div)" "${KTSTOP}" "${KTMAX}" >"${sum}"
  exit 0
fi

# ---------------------------------------------------------------------------
# One control-voltage calibration point.
#   --one-vpre <bundle> <temp> <vdd> <band> <vctrl-predicted> <fout> <fref> <out>
#
# Runs the steady-state deck TWICE with VCTRL forced, at v0 and v0 + KVPRE_D,
# and solves the two measured (Vctrl, f_out) points for the control voltage
# that gives <fout>.  Writes "<v_solved> <f_at_v0> <f_at_v1>".
# ---------------------------------------------------------------------------
if [ "${1:-}" = "--one-vpre" ]; then
  shift
  bundle="$1"; temp="$2"; vdd="$3"; band="$4"; vc0="$5"; fout="$6"; fref="$7"; out="$8"
  libs="$(libs_for "${bundle}")"
  # The frequency belongs IN the work-directory name, exactly as it does for
  # --one-lock.  Without it the KFOUT and KFOUT2 calibrations of the same
  # (bundle, temp, vdd) share one directory -- and since both job sets are in
  # the same xargs pass, two ngspice processes write the same ngspice.log at
  # the same time.  The .sig guard stops the WRONG cached run being reused, but
  # nothing stops two concurrent runs interleaving into one log, which reads
  # back as a failed measurement or, worse, as a plausible wrong number.
  kind="f$(awk -v f="${fout}" 'BEGIN{printf "%03d", f/1e6}')"
  vpre_point() {
    local vv="$1" idx="$2" ts="$3"
    local tag="vpre${idx}_${kind}_${bundle}_T${temp}_V${vdd}"
    # A retry at the longer window gets its OWN work directory, so it adds a
    # measurement rather than overwriting the one it is replacing.
    [ "${ts}" = "$(vpre_tstop_for "${fout}")" ] || tag="${tag}_X${ts}"
    tag=$(simenv_mktag "${tag}")
    local rundir="${WORK}/${tag}" log="${WORK}/${tag}/ngspice.log"
    local params=( "vsup=${vdd}" "fref=${fref}" "nratio=${KN}" "vctrl0=${vv}"
                   "rforce=${KVPRE_RON}"
                   "tstop=${ts}" "tstep=${KTSTEP}" "tmax=${KTMAX}"
                   "ta=${KVPRE_TA}" "tb=${KVPRE_TB}" )
    # shellcheck disable=SC2207
    params+=( $(cloop_band_params "${band}") )
    # shellcheck disable=SC2207
    params+=( $(cloop_trim_params "${KTRIM}") )
    # shellcheck disable=SC2207
    params+=( $(cloop_divider_params "${KN}") )
    local sig="${libs}|${temp}|${params[*]}"
    if [ -z "${SIM_FORCE:-}" ] && [ -f "${log}" ] && [ "${log}" -nt "${DUT_LOCK}" ] \
       && [ "$(cat "${rundir}/.sig" 2>/dev/null)" = "${sig}" ] \
       && grep -q "Total analysis time" "${log}" 2>/dev/null; then
      :
    else
      simenv_run_deck "${DUT_LOCK}" "${WORK}" "${tag}" "${libs}" "${temp}" "${params[@]}" \
        >/dev/null 2>&1 || true
      grep -q "Total analysis time" "${log}" 2>/dev/null || {
        echo "ERROR: ngspice did not complete ${tag} (see ${log})" >&2; exit 1; }
      printf '%s' "${sig}" >"${rundir}/.sig"
    fi
    simenv_meas "${log}" fout
  }
  vc1="$(awk -v a="${vc0}" -v d="${KVPRE_D}" 'BEGIN{printf "%.4f", a+d}')"
  TS_N="$(vpre_tstop_for "${fout}")"
  TS_X="$(vpre_tstop_retry_for "${fout}")"
  f0="$(vpre_point "${vc0}" 0 "${TS_N}")"
  f1="$(vpre_point "${vc1}" 1 "${TS_N}")"
  # A `failed` f_out measurement means the forced point ran slower than the
  # window assumed, not that the VCO is broken -- re-measure it longer.
  [ "${f0}" = "nan" ] && f0="$(vpre_point "${vc0}" 0 "${TS_X}")"
  [ "${f1}" = "nan" ] && f1="$(vpre_point "${vc1}" 1 "${TS_X}")"
  awk -v v0="${vc0}" -v v1="${vc1}" -v f0="${f0}" -v f1="${f1}" -v ft="${fout}" \
      -v lo="${KVPRE_LO}" -v hi="${KVPRE_HI}" 'BEGIN{
    if (f0 == "nan" || f1 == "nan" || f1 == f0) { printf "%s %s %s\n", "nan", f0, f1; exit }
    v = v0 + (ft - f0) * (v1 - v0) / (f1 - f0);
    if (v < lo) v = lo; if (v > hi) v = hi;
    printf "%.4f %.6g %.6g\n", v, f0, f1;
  }' >"${out}"
  exit 0
fi

# ---------------------------------------------------------------------------
# One supply step/ramp run.
#   --one-dyn <bundle> <temp> <band> <vctrl0> <sumfile> <wavefile>
# ---------------------------------------------------------------------------
if [ "${1:-}" = "--one-dyn" ]; then
  shift
  bundle="$1"; temp="$2"; band="$3"; vc0="$4"; sum="$5"; wave="$6"
  tag="dyn_${bundle}_T${temp}"; tag=$(simenv_mktag "${tag}")
  rundir="${WORK}/${tag}"; log="${rundir}/ngspice.log"
  libs="$(libs_for "${bundle}")"

  # Snap every phase probe onto a reference HALF-period, tstart + (k+0.5)/f_ref
  # with tstart = 0.5/f_ref, so REF and FB rises paired by a probe are the same
  # cycle's and the measurement cannot alias by a whole reference period.
  snap() { awk -v t="$1" -v f="${KFREF}" \
    'BEGIN{ tr=1/f; ts=0.5*tr; k=int((t-ts)/tr - 0.5 + 0.5); if(k<0)k=0;
            printf "%.12g", ts + (k+0.5)*tr }'; }
  P=()
  for t in 2.4e-6 4.0e-6 5.92e-6 6.72e-6 8.0e-6 11.2e-6 12.8e-6 14.4e-6 18.4e-6 21.6e-6 24.0e-6 28.8e-6; do
    P+=( "$(snap "${t}")" )
  done

  params=( "vsup=${KD_LO}" "fref=${KFREF}" "nratio=${KN}" "vctrl0=${vc0}"
           "v_lo=${KD_LO}" "v_hi=${KD_HI}" "v_end=${KD_END}"
           "t_step=${KD_TSTEP}" "t_edge=${KD_TEDGE}"
           "t_ramp=${KD_TRAMP}" "t_rend=${KD_TREND}"
           "tstop=${KD_TSTOP}" "tstep=${KTSTEP}" "tmax=${KTMAX}" )
  for i in $(seq 0 11); do params+=( "p$((i+1))=${P[${i}]}" ); done
  # shellcheck disable=SC2207
  params+=( $(cloop_band_params "${band}") )
  # shellcheck disable=SC2207
  params+=( $(cloop_trim_params "${KTRIM}") )
  # shellcheck disable=SC2207
  params+=( $(cloop_divider_params "${KN}") )
  sig="${libs}|${temp}|${params[*]}"

  if [ -z "${SIM_FORCE:-}" ] && [ -f "${log}" ] && [ "${log}" -nt "${DUT_DYN}" ] \
     && [ "$(cat "${rundir}/.sig" 2>/dev/null)" = "${sig}" ] \
     && grep -q "Total analysis time" "${log}" 2>/dev/null; then
    :
  else
    simenv_run_deck "${DUT_DYN}" "${WORK}" "${tag}" "${libs}" "${temp}" "${params[@]}" \
      >/dev/null 2>&1 || true
    grep -q "Total analysis time" "${log}" 2>/dev/null || {
      echo "ERROR: ngspice did not complete ${tag} (see ${log})" >&2; exit 1; }
    printf '%s' "${sig}" >"${rundir}/.sig"
  fi

  m() { simenv_meas "${log}" "$1"; }
  {
    printf '%s,%s,%s,%s' "${bundle}" "${temp}" "${band}" "${vc0}"
    for k in phi01 phi02 phi03 phi04 phi05 phi06 phi07 phi08 phi09 phi10 phi11 phi12 \
             ferr_lo ferr_hi ferr_end fout_lo fout_hi fout_end fout_s fout_r \
             vc_lo vc_hi vc_end vc_smax vc_smin vc_rmax vc_rmin vc_all_max vc_all_min \
             lock_lo lock_stp lock_hi lock_rmp lock_end lock_min \
             i_core_lo i_vco_lo i_div_lo i_core_hi i_vco_hi i_div_hi \
             i_core_end i_vco_end i_div_end; do
      printf ',%s' "$(m "${k}")"
    done
    printf '\n'
  } >"${sum}"

  # sim/README.md's waveform rule: the disturbance transient IS the argument
  # for this criterion, so keep it -- decimated, as a CSV of the four signals
  # that carry it, never as a rawfile.  Nearest-sample decimation, no
  # interpolation, so every committed row is a value ngspice computed.
  {
    echo "# gf180-pll :: supply-sensitivity :: supply step/ramp transient"
    echo "# corner: ${bundle} / ${temp} C, band ${band}, N=${KN}, f_ref=${KFREF} Hz"
    echo "# profile: ${KD_LO} V -> step(${KD_TEDGE}) -> ${KD_HI} V @ ${KD_TSTEP};"
    echo "#          ramp ${KD_TRAMP}..${KD_TREND} -> ${KD_END} V; hold to ${KD_TSTOP}"
    echo "# decimation: nearest sample at ${KD_DECIM} s from the full ngspice trace"
    echo "t_s,vctrl_v,lock_v,vdd_v,fb_v"
    awk -v d="${KD_DECIM}" '
      /^[ \t]*[-0-9]/ {
        t = $1 + 0;
        if (t + 1e-15 >= next_t) {
          printf "%.9g,%.6g,%.6g,%.6g,%.6g\n", t, $2, $4, $6, $8;
          next_t = t + d;
        }
      }' "${rundir}/supply_transient_full.csv"
  } >"${wave}"
  exit 0
fi

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
simenv_require_tools
[ -f "${VCO_TUNING}" ] || {
  echo "ERROR: ${VCO_TUNING} missing -- this campaign derives its operating" >&2
  echo "       point from #8's committed f(Vctrl) evidence, not from a fresh sweep." >&2
  exit 1; }

mkdir -p "${WORK}"
cloop_assemble "${HERE}/tb_supply_lock.sp" "${DUT_LOCK}"
cloop_assemble "${HERE}/tb_supply_dyn.sp"  "${DUT_DYN}"

OPTAB="${WORK}/op_100.csv"
OPTAB2="${WORK}/op_050.csv"
derive_op_points "${KFOUT}"  >"${OPTAB}"
derive_op_points "${KFOUT2}" >"${OPTAB2}"

if [ "${1:-}" = "--op-table" ]; then
  echo "operating points for f_out = ${KFOUT} Hz  (bundle,temp,band,vctrl@2.97,@3.30,@3.63)"
  cat "${OPTAB}"
  echo
  echo "operating points for f_out = ${KFOUT2} Hz"
  cat "${OPTAB2}"
  exit 0
fi

if [ "${1:-}" = "--check" ]; then
  read -r _b _t band v297 v330 v363 <<<"$(awk -F, '$1=="typical"&&$2=="27"{print $1,$2,$3,$4,$5,$6}' "${OPTAB}")"
  echo "supply-sensitivity --check: typical/27C/3.30V, band ${band}, vctrl0 ${v330}"
  tmp="$(mktemp)"
  "${HERE}/run.sh" --one-lock typical 27 3.30 "${band}" "${v330}" "${KFOUT}" "${KFREF}" "${tmp}"
  cat "${tmp}"; rm -f "${tmp}"
  echo "supply-sensitivity: --check, no record written"
  exit 0
fi

# --- pre-pass: the in-loop control voltage for every point we intend to run ---
# #8's f(Vctrl) is a STANDALONE-VCO measurement and does not transfer to the
# VCO as loaded inside pll_top (see the `rforce` note in tb_supply_lock.sp), so
# every closed-loop point's warm start is calibrated first against this DUT.
JOBSPRE="${WORK}/jobs_vpre.txt"; : >"${JOBSPRE}"
NOBAND=""
emit_pre() {  # <bundle> <temp> <band> <v297> <v330> <v363> <fout> <fref> <slug>
  local b="$1" t="$2" bd="$3" fo="$7" fr="$8" sl="$9"
  local i=0 vv
  for vv in "$4" "$5" "$6"; do
    i=$((i+1))
    local vdd; vdd="$(awk -v i="${i}" 'BEGIN{split("2.97 3.30 3.63",a," "); print a[i]}')"
    echo "${b} ${t} ${vdd} ${bd} ${vv} ${fo} ${fr} ${WORK}/vpre_${sl}_${b}_${t}_${vdd}.txt" >>"${JOBSPRE}"
  done
}
while IFS=, read -r bundle temp band v297 v330 v363; do
  in_list "${bundle}" "${GRID_BUNDLES}" || continue
  in_list "${temp}"   "${GRID_TEMPS}"   || continue
  if [ "${band}" = "-1" ]; then
    NOBAND="${NOBAND}${bundle}/${temp}C "
    continue
  fi
  emit_pre "${bundle}" "${temp}" "${band}" "${v297}" "${v330}" "${v363}" "${KFOUT}" "${KFREF}" 100
done <"${OPTAB}"
while IFS=, read -r bundle temp band v297 v330 v363; do
  in_list "${bundle}" "${SPLIT_BUNDLES}" || continue
  in_list "${temp}"   "${SPLIT_TEMPS}"   || continue
  in_list "${bundle}" "${GRID_BUNDLES}"  || continue
  in_list "${temp}"   "${GRID_TEMPS}"    || continue
  [ "${band}" = "-1" ] && continue
  emit_pre "${bundle}" "${temp}" "${band}" "${v297}" "${v330}" "${v363}" "${KFOUT2}" "${KFREF2}" 050
done <"${OPTAB2}"

NPRE=$(wc -l <"${JOBSPRE}" | tr -d ' ')
echo "supply-sensitivity: ${NPRE} in-loop control-voltage calibration runs (2 forced points each)"
# shellcheck disable=SC2016
xargs -P "$(simenv_jobs)" -L 1 \
  "${BASH:-/bin/bash}" -c 'exec "$0" --one-vpre "$@"' "${HERE}/run.sh" <"${JOBSPRE}"

vpre_of() {  # <slug> <bundle> <temp> <vdd> -> calibrated control voltage
  awk '{print $1}' "${WORK}/vpre_$1_$2_$3_$4.txt" 2>/dev/null
}

# --- job list: the steady-state grid at 100 MHz -----------------------------
JOBS100="${WORK}/jobs_100.txt"; : >"${JOBS100}"
while IFS=, read -r bundle temp band v297 v330 v363; do
  in_list "${bundle}" "${GRID_BUNDLES}" || continue
  in_list "${temp}"   "${GRID_TEMPS}"   || continue
  [ "${band}" = "-1" ] && continue
  for vdd in 2.97 3.30 3.63; do
    vc="$(vpre_of 100 "${bundle}" "${temp}" "${vdd}")"
    [ -n "${vc}" ] && [ "${vc}" != "nan" ] || { echo "ERROR: no calibrated Vctrl for ${bundle}/${temp}C/${vdd}V" >&2; exit 1; }
    echo "${bundle} ${temp} ${vdd} ${band} ${vc} ${KFOUT} ${KFREF} ${WORK}/s100_${bundle}_${temp}_${vdd}.csv" >>"${JOBS100}"
  done
done <"${OPTAB}"

# --- job list: the quiescent/dynamic power split -----------------------------
# QUIESCENT VS. DYNAMIC.  There is no "switch the clock off" state to measure a
# quiescent current in: the ring VCO's starving current IS its oscillation
# current, and a PLL with a stopped reference is not a locked PLL.  So the
# split is measured the way it is defined -- as the frequency-INDEPENDENT and
# frequency-PROPORTIONAL parts of the same current -- by locking the same loop
# at a second output frequency and fitting I(f) = I_q + k*f per domain.  The
# second point halves BOTH f_out and f_ref, so every switching node in the
# block scales together and the fit has one slope rather than two.
#
# Reduced grid, and why: the split is a decomposition of a total the 45-point
# grid above already reports at every corner, and its own corner dependence is
# second-order (it re-attributes the same measured current between two
# columns).  It is run over the supply and temperature axes at the `typical`
# process bundle -- 9 points -- so the supply axis this campaign exists to
# sweep is covered at full resolution.
JOBS050="${WORK}/jobs_050.txt"; : >"${JOBS050}"
while IFS=, read -r bundle temp band v297 v330 v363; do
  in_list "${bundle}" "${SPLIT_BUNDLES}" || continue
  in_list "${temp}"   "${SPLIT_TEMPS}"   || continue
  in_list "${bundle}" "${GRID_BUNDLES}"  || continue
  in_list "${temp}"   "${GRID_TEMPS}"    || continue
  [ "${band}" = "-1" ] && continue
  for vdd in 2.97 3.30 3.63; do
    vc="$(vpre_of 050 "${bundle}" "${temp}" "${vdd}")"
    [ -n "${vc}" ] && [ "${vc}" != "nan" ] || continue
    echo "${bundle} ${temp} ${vdd} ${band} ${vc} ${KFOUT2} ${KFREF2} ${WORK}/s050_${bundle}_${temp}_${vdd}.csv" >>"${JOBS050}"
  done
done <"${OPTAB2}"

# --- job list: supply step/ramp ---------------------------------------------
# Three corners, chosen as the extremes of the steady-state grid rather than as
# a convenience sample: nominal, the slow/cold corner and the fast/hot corner.
# Justified in the record; the step/ramp criterion is a stays-locked question,
# and a corner at which the loop stays locked through the profile at both
# extremes of process and temperature answers it in a way 45 repetitions of the
# same answer would not improve.
JOBSDYN="${WORK}/jobs_dyn.txt"; : >"${JOBSDYN}"
set -- ${DYN_PICKS}
while [ "$#" -ge 2 ]; do
  b="$1"; t="$2"; shift 2
  row="$(awk -F, -v b="${b}" -v t="${t}" '$1==b && $2==t {print}' "${OPTAB}")"
  [ -n "${row}" ] || continue
  band="$(echo "${row}" | cut -d, -f3)"
  [ "${band}" = "-1" ] && continue
  v330="$(vpre_of 100 "${b}" "${t}" 3.30)"
  [ -n "${v330}" ] && [ "${v330}" != "nan" ] || continue
  echo "${b} ${t} ${band} ${v330} ${WORK}/sdyn_${b}_${t}.csv ${WORK}/wave_${b}_${t}.csv" >>"${JOBSDYN}"
done

N100=$(wc -l <"${JOBS100}" | tr -d ' ')
N050=$(wc -l <"${JOBS050}" | tr -d ' ')
NDYN=$(wc -l <"${JOBSDYN}" | tr -d ' ')
echo "supply-sensitivity: ${N100} steady-state runs @ ${KFOUT} Hz, ${N050} @ ${KFOUT2} Hz (power split), ${NDYN} step/ramp runs; $(simenv_jobs) parallel jobs"
[ -z "${NOBAND}" ] || echo "supply-sensitivity: NO single band spans +/-10 % at: ${NOBAND}"

# The step/ramp runs go FIRST: each is a ${KD_TSTOP} transient against the
# grid's ${KTSTOP}, so starting them last would leave one long job running
# alone at the end with the machine idle behind it.
# shellcheck disable=SC2016
xargs -P "$(simenv_jobs)" -L 1 \
  "${BASH:-/bin/bash}" -c 'exec "$0" --one-dyn "$@"' "${HERE}/run.sh" <"${JOBSDYN}" &
DYNPID=$!
# shellcheck disable=SC2016
xargs -P "$(simenv_jobs)" -L 1 \
  "${BASH:-/bin/bash}" -c 'exec "$0" --one-lock "$@"' "${HERE}/run.sh" <"${JOBS100}"
# shellcheck disable=SC2016
xargs -P "$(simenv_jobs)" -L 1 \
  "${BASH:-/bin/bash}" -c 'exec "$0" --one-lock "$@"' "${HERE}/run.sh" <"${JOBS050}"

# --- settling escalation ----------------------------------------------------
# A corner whose measured residual frequency error exceeds ACC_FERR at the
# default transient length has not been shown to FAIL the lock criterion; it
# has been shown to be still converging, and those are different claims.  The
# distinction is a design question -- `sim/loop-dynamics` (#10) predicts phase
# margin falling as Icp*Kvco/N rises, so the corners that ring longest are
# expected to be the highest-Kvco operating points -- and it is settled by
# running the SAME corner longer and comparing the two residuals, not by
# reading the short run harder.  So the runner does it itself: escalation is
# mechanism, not a note in the record asking someone to follow up.
#
#   SIM_EXTEND=off        skip the escalation entirely
#   SIM_EXTEND_TSTOP/_TA/_TB   the longer transient (default 36.8u/31.2u/34.4u)
#   SIM_EXTEND_MAX=<n>    cap the number of escalated corners (compute budget);
#                         the worst residuals are escalated first, and
#                         report.sh states the cap in the record when it bites.
JOBS100X="${WORK}/jobs_100x.txt"; : >"${JOBS100X}"
if [ "${SIM_EXTEND:-auto}" != "off" ]; then
  cat "${WORK}"/s100_*.csv 2>/dev/null | awk -F, -v accf="${ACC_FERR}" -v w="${WORK}" \
      -v fo="${KFOUT}" -v fr="${KFREF}" '
    { fe = $13 + 0; if (fe < 0) fe = -fe;
      if (fe > accf) printf "%.6g %s %s %s %s %s %s %s %s/s100x_%s_%s_%s.csv\n",
        fe, $1, $2, $3, $5, $9, fo, fr, w, $1, $2, $3 }' \
    | sort -rn | cut -d' ' -f2- \
    | { if [ -n "${SIM_EXTEND_MAX:-}" ]; then head -n "${SIM_EXTEND_MAX}"; else cat; fi } \
    >"${JOBS100X}"
fi
NX=$(wc -l <"${JOBS100X}" | tr -d ' ')
if [ "${NX}" -gt 0 ]; then
  echo "supply-sensitivity: ${NX} corner(s) still converging at ${KTSTOP} -- re-running at ${KTSTOP_X}"
  # shellcheck disable=SC2016
  SIM_TSTOP="${KTSTOP_X}" SIM_TA="${KTA_X}" SIM_TB="${KTB_X}" \
    xargs -P "$(simenv_jobs)" -L 1 \
      "${BASH:-/bin/bash}" -c 'exec "$0" --one-lock "$@"' "${HERE}/run.sh" <"${JOBS100X}"
fi

# --- timestep-ceiling cross-check -------------------------------------------
# The escalation above buys the right to say "this corner is not merely slow".
# It does NOT by itself buy the right to say "this corner is under-damped",
# because a third explanation exists and PR #64 measured it on this exact DUT:
# the integration stepping over `design/edgedet.sch`'s 0.33-0.39 ns internal PFD
# set pulse, which reads out as a loop that will not converge.  A design-margin
# finding routed to #10 or #8 on the strength of a numerical artefact is the
# most expensive mistake this campaign can make -- a real claim about the design,
# made from a simulator setting.
#
# With KTMAX at the shared bound (the normal case) that explanation is already
# excluded and this stage does nothing.  It exists for the one case where it is
# not: a deliberate bound-sensitivity run (`SIM_TMAX`, the only use
# `sim/lib/simenv.sh` sanctions), where the grid ran coarser than the bound.
# Then every corner still over ACC_FERR after the escalation is re-run at
# KTSTOP_X *and* at the bound, and report.sh classifies a corner that comes
# inside the criterion there as `integration`, not as `under-damped`.
#
#   SIM_FINE=off          skip the cross-check (a record that skips it says so)
#   SIM_FINE_TMAX=<t>     the ceiling it re-runs at (default: the bound)
#   SIM_FINE_MAX=<n>      cap how many corners are cross-checked
JOBS100M="${WORK}/jobs_100m.txt"; : >"${JOBS100M}"
if [ "${SIM_FINE:-auto}" != "off" ] && [ "${KTMAX_X}" != "${KTMAX}" ]; then
  cat "${WORK}"/s100x_*.csv 2>/dev/null | awk -F, -v accf="${ACC_FERR}" -v w="${WORK}" \
      -v fo="${KFOUT}" -v fr="${KFREF}" '
    { fe = $13 + 0; if (fe < 0) fe = -fe;
      if (fe > accf) printf "%.6g %s %s %s %s %s %s %s %s/s100m_%s_%s_%s.csv\n",
        fe, $1, $2, $3, $5, $9, fo, fr, w, $1, $2, $3 }' \
    | sort -rn | cut -d' ' -f2- \
    | { if [ -n "${SIM_FINE_MAX:-}" ]; then head -n "${SIM_FINE_MAX}"; else cat; fi } \
    >"${JOBS100M}"
fi
NM=$(wc -l <"${JOBS100M}" | tr -d ' ')
if [ "${NM}" -gt 0 ]; then
  echo "supply-sensitivity: ${NM} corner(s) still over ${ACC_FERR} at ${KTSTOP_X} -- re-running at timestep ceiling ${KTMAX_X}"
  # shellcheck disable=SC2016
  SIM_TSTOP="${KTSTOP_X}" SIM_TA="${KTA_X}" SIM_TB="${KTB_X}" SIM_TMAX="${KTMAX_X}" \
    xargs -P "$(simenv_jobs)" -L 1 \
      "${BASH:-/bin/bash}" -c 'exec "$0" --one-lock "$@"' "${HERE}/run.sh" <"${JOBS100M}"
fi

wait "${DYNPID}"

got100=$(cat "${WORK}"/s100_*.csv 2>/dev/null | wc -l | tr -d ' ')
got050=$(cat "${WORK}"/s050_*.csv 2>/dev/null | wc -l | tr -d ' ')
gotdyn=$(cat "${WORK}"/sdyn_*.csv 2>/dev/null | wc -l | tr -d ' ')
[ "${got100}" -eq "${N100}" ] || { echo "ERROR: expected ${N100} rows @100 MHz, got ${got100}" >&2; exit 1; }
[ "${got050}" -eq "${N050}" ] || { echo "ERROR: expected ${N050} rows @50 MHz, got ${got050}" >&2; exit 1; }
[ "${gotdyn}" -eq "${NDYN}" ] || { echo "ERROR: expected ${NDYN} step/ramp rows, got ${gotdyn}" >&2; exit 1; }
got100x=$(cat "${WORK}"/s100x_*.csv 2>/dev/null | wc -l | tr -d ' ')
[ "${got100x}" -eq "${NX}" ] || { echo "ERROR: expected ${NX} settling re-run rows, got ${got100x}" >&2; exit 1; }
got100m=$(cat "${WORK}"/s100m_*.csv 2>/dev/null | wc -l | tr -d ' ')
[ "${got100m}" -eq "${NM}" ] || { echo "ERROR: expected ${NM} timestep-ceiling rows, got ${got100m}" >&2; exit 1; }

exec "${HERE}/report.sh" "${WORK}" "${EXP}" "${HERE}"
