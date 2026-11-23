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
#   SIM_WINTRIM=<0..15>      run every corner at ONE forced lock-detector window
#                            trim code instead of the code `spec/pll.md`'s
#                            trim-code rule selects per bundle (see KWINTRIM
#                            below).  Such a run gets its own work directory --
#                            the "_W<code>" tag -- so a forced-code run and the
#                            rule-selected run it exists to be compared with
#                            keep their logs side by side instead of one
#                            overwriting the other (#425).
#
#   The step/ramp deck has TWO independent settling escalations, one per
#   plateau, because a corner can still be converging after the STEP, after
#   the RAMP, or both, and those are different claims:
#
#   SIM_DYN_TRAMP/_TREND/_TSTOP/_TA_HI/_TB_HI
#                            override the step/ramp profile and its
#                            HIGH-plateau (post-STEP) measurement window.
#   SIM_DYN_EXTEND=off       disable the automatic HIGH-plateau escalation
#                            (#253); SIM_DYN_EXTEND_TA/_TB/_TRAMP/_TREND/_TSTOP
#                            are the longer profile it escalates to and
#                            SIM_DYN_EXTEND_MAX=<n> caps how many corners it
#                            reaches.
#   SIM_DYN_P11 / SIM_DYN_P12
#                            override the two END-plateau (post-RAMP)
#                            measurement instants, the criterion-3 analogue of
#                            SIM_TA/SIM_TB above (#255).  Unset = derived from
#                            the profile, exactly as this deck has always done.
#   SIM_DYN_END_EXTEND=off   disable the automatic END-plateau settling
#                            escalation (#255); SIM_DYN_END_MAX=<n> caps how
#                            many step/ramp corners it escalates.
#   SIM_DYN_END_TA/_TB/_TSTOP  the two probe instants and the post-ramp hold
#                            it escalates to, stated as OFFSETS FROM t_rend so
#                            they compose with the HIGH-plateau escalation
#                            (defaults: KTA_X/KTB_X/KTSTOP_X -- see
#                            "END-plateau settling escalation" below).
#
#   Every step/ramp run writes TWO artefacts next to each other (#395): the
#   decimated four-signal transient it always wrote (<wavefile>), and a
#   per-REFERENCE-CYCLE REF->FB phase trace (<wavefile minus .csv>_phase.csv)
#   covering the whole profile.  The second exists because the post-step
#   settling question is about a few nanoseconds of edge-to-edge skew, which a
#   decimated v(fb) sample does not carry, and because the twelve phi01..phi12
#   point samples put only TWO of themselves on the high plateau -- too few to
#   tell a single-pole decay from an under-damped one (DR-011 Decision 2).
#   See the "--- per-REF-cycle phase trace" block in --one-dyn below.
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
#   SIM_SUBSET_NOTE='<why>'  the in-record justification for running fewer than
#                            the 45 default points.  `sim/README.md` allows a
#                            subset "only with an in-record justification" and
#                            rejects "the sim was slow" as one, so the reason
#                            has to travel with the RUN that chose the subset
#                            rather than being a fixed paragraph describing one
#                            historical reduction.  Unset keeps that historical
#                            paragraph, which is correct only for a run of that
#                            same shape (process axis cut, temperature and
#                            supply whole).
#   SIM_XING_PICKS='<b>|<t>|<v> ...'
#                            the cells section 1d answers DR-013's
#                            window-vs-offset crossing question at.  Default is
#                            the two cells DR-013 itself names.  A cell not
#                            actually swept is absent from that section rather
#                            than answered.
#
# Every run is resumable: a completed run is reused only on an exact match of
# the deck mtime AND the full parameter list, never on the deck alone.

set -euo pipefail
# The settling-escalation and timestep-cross-check glob patterns below
# (s100x_*.csv, s100m_*.csv, sdynx_*.csv, sdynend_*.csv) legitimately match
# zero files whenever every corner already met the lock criterion at the
# default transient length --
# the common, good-path outcome, not an error.  Without nullglob, an
# unmatched glob expands to its own literal pattern, `cat` fails to open a
# file with that literal name, and -- because that `cat` sits at the head of
# a `| wc -l | tr -d ' '` pipeline under `pipefail` -- the pipeline's exit
# status is `cat`'s failure, which `set -e` treats as this whole script
# failing, silently (no message; report.sh, which mints the record, is never
# reached).  This is the same rationale report.sh already states for its own
# identical `shopt -s nullglob` (see its header).
shopt -s nullglob

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP="$(cd "${HERE}/.." && pwd)"
ROOT="$(cd "${EXP}/../.." && pwd)"
# shellcheck source=../../lib/simenv.sh
. "${ROOT}/sim/lib/simenv.sh"
# shellcheck source=../../lib/pll_top_dut.sh
. "${ROOT}/sim/lib/pll_top_dut.sh"
# The campaign's settings (operating point, transients, acceptance
# thresholds, citations) and the window-trim helpers the runner and the
# reporter share live in settings.sh beside this script.  Sourced here, after
# ROOT and simenv.sh exist, because settings.sh itself depends on both.
# shellcheck source=settings.sh
. "${HERE}/settings.sh"

WORK="${EXP}/work"
DUT_LOCK="${WORK}/dut_lock.sp"
DUT_DYN="${WORK}/dut_dyn.sp"

# The corner axes.  Default is the full 45-point grid sim/README.md prescribes.
# SIM_BUNDLES / SIM_TEMPS narrow it for a compute-limited run; whatever is
# actually swept is what report.sh writes into the record's corner-matrix
# field, derived from the collected rows rather than from these defaults, so a
# reduced run can never describe itself as a full one.
GRID_BUNDLES="${SIM_BUNDLES:-typical ff ss fs sf}"
GRID_TEMPS="${SIM_TEMPS:--40 27 125}"
# SIM_PICKS names explicit `<bundle> <temp>` PAIRS instead of the rectangle
# SIM_BUNDLES x SIM_TEMPS, for a question that is about particular cells rather
# than about a sub-grid -- e.g. DR-013's crossing check, which is about
# `typical`/-40 C and `ff`/27 C and about no other cell of the grid.  Spelling
# that as a rectangle would cost two irrelevant corners at ~3.2 h of ngspice
# each.  Empty (the default) leaves the rectangle in charge; the two knobs
# compose, with SIM_PICKS applied on top.
GRID_PICKS="${SIM_PICKS:-}"
# The corners the step/ramp deck runs at, and the corners the second frequency
# point of the power split runs at.  Both are subsets by design (see the
# record's Methodology), and both are overridable for the same reason.
DYN_PICKS="${SIM_DYN_PICKS:-typical 27}"
SPLIT_BUNDLES="${SIM_SPLIT_BUNDLES:-typical}"
SPLIT_TEMPS="${SIM_SPLIT_TEMPS:-27}"

in_list() { case " $2 " in *" $1 "*) return 0 ;; *) return 1 ;; esac }

# in_grid <bundle> <temp> -- is this cell of the PVT grid in scope for this run?
in_grid() {
  if [ -n "${GRID_PICKS}" ]; then
    case " ${GRID_PICKS} " in *" $1 $2 "*) return 0 ;; *) return 1 ;; esac
  fi
  in_list "$1" "${GRID_BUNDLES}" || return 1
  in_list "$2" "${GRID_TEMPS}"   || return 1
  return 0
}

# ---------------------------------------------------------------------------
# Operating-point derivation
# ---------------------------------------------------------------------------
# For each (bundle, temperature) pick ONE band code -- band select is a static
# input with no calibration FSM (DR-001 Decision 2), so it cannot be re-chosen
# when the supply moves, and picking it per supply would measure a different
# configuration at each supply point and call the difference "supply
# sensitivity".  The chosen code is **the lowest band code that reaches the
# target frequency at all three supplies inside the control window** -- i.e.
# `spec/pll.md`'s normative [Band-selection rule], applied rather than
# approximated.  The per-supply control voltage it implies is the warm start.
#
# THIS USED TO BE A MID-WINDOW HEURISTIC, AND THE DIFFERENCE MATTERED (#511,
# DR-025).  Until that issue this function picked the band whose control
# voltage was closest to the midpoint of the search window -- a selector that
# is not the rule and was the only band selector in `sim/` that was not
# (`sim/pll-top-smoke` states and applies the rule by name).  The two agree at
# 14 of the 15 (bundle, temperature) cells at KFOUT, and disagree at exactly
# one: `ff`/27 C, where the heuristic chose band 6 (Vctrl 1.008-1.394 V) and
# the rule chooses band 5 (1.967-2.595 V).  That is the cell carrying the
# largest settled violation of the ratified <= 1 ns Lock criterion on the
# committed grid (1.227 ns at 3.63 V), and the open-loop systematic term
# `sim/pfd-deadzone` measures at the two control voltages differs by 2.7x -- so
# the heuristic was measuring a configuration no compliant part carries, at the
# one cell where it changes a spec verdict.  See
# `sim/supply-sensitivity/records/20260925-090649-4422f1d.md`.
#
# THE WINDOW IS DR-003 DECISION 5'S **MEASURED** 0.9-2.7 V, not DR-001
# Decision 2's predicted 0.9-2.4 V.  `spec/pll.md` states the rule without
# naming a window, and the choice is load-bearing: under the predicted window
# the rule has NO answer at 4 of the 15 cells at 100 MHz (no single static band
# reaches it across the ratified rail without leaving that window), so the
# measured window is the only reading under which the rule is satisfiable.
# The old default bottom edge was 0.85 V, 50 mV below either ratified window.
#
# Prints: bundle,temp_c,band,vctrl_2.97,vctrl_3.30,vctrl_3.63
# A (bundle, temperature) row for which NO band reaches the target at all three
# supplies inside the window is printed with band = -1, and the caller treats
# that as a campaign-level finding rather than papering over it.
#
# Where the rule and the retired heuristic disagree, a note is written to
# stderr naming the cell and both bands, so a run that lands on the one
# contested cell says so in its own log rather than only in this comment.
derive_op_points() {
  local target="$1" lo="${2:-0.90}" hi="${3:-2.70}"
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
        # ruleband: the LOWEST feasible code -- the normative rule.
        # heurband: the retired mid-window pick, computed only so a
        #           disagreement can be REPORTED; it never sets the answer.
        ruleband = -1; ruleline = ",,,";
        heurband = -1; heurcost = 1e9;
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
          if (!ok) continue;
          if (ruleband == -1) { ruleband = bd; ruleline = line }
          if (cost < heurcost) { heurcost = cost; heurband = bd }
        }
        if (ruleband != -1 && heurband != -1 && ruleband != heurband)
          printf "supply-sensitivity: band-selection rule picks B%d at %s/%s C" \
                 " (the retired mid-window heuristic picked B%d) -- see DR-025\n", \
                 ruleband, BU[bi], TE[ti], heurband > "/dev/stderr";
        printf "%s,%s,%d%s\n", BU[bi], TE[ti], ruleband, ruleline;
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
  # ... and so does a non-default lock-detector window trim code, on the same
  # rule and for the same reason (#425).  The suffix names the KWINTRIM SETTING,
  # not the per-corner resolved code -- see window_trim_tag_suffix() for why
  # (`rule` has to stay unsuffixed, and the two agree wherever a suffix is
  # emitted at all).
  tag="${tag}$(window_trim_tag_suffix)"
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
  params+=( $(cloop_window_trim_params "$(window_trim_code_of "${bundle}")") )
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
    # The calibration deck is a closed-loop run too, so it carries the window
    # trim code (below) and needs the same per-code directory split as
    # --one-lock (#425).  Suffix names the KWINTRIM SETTING, not the per-corner
    # resolved code -- rationale at window_trim_tag_suffix().
    tag="${tag}$(window_trim_tag_suffix)"
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
    params+=( $(cloop_window_trim_params "$(window_trim_code_of "${bundle}")") )
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
  tag="dyn_${bundle}_T${temp}"
  # A non-default hold (the criterion-3 escalation, #253) gets its own work
  # directory -- so the longer-hold re-run ADDS evidence rather than
  # overwriting the default-hold run it is compared against, exactly as the
  # criterion-1 escalation's "_X${KTSTOP}" tag does for --one-lock.
  [ "${KD_TRAMP}" = "${KD_TRAMP_BASE}" ] || tag="${tag}_X${KD_TRAMP}"
  # ... and a non-default END-plateau hold (the criterion-3 END escalation,
  # #255) gets its own directory again, on the SAME rule and for the same
  # reason.  The two suffixes compose: a corner escalated on both plateaus
  # lands in "..._X<t_ramp>_E<p12>", distinct from either single escalation.
  [ -z "${KD_P12}" ] || tag="${tag}_E${KD_P12}"
  # The step/ramp deck carries the window trim code as well, so a non-default
  # code gets its own directory here too, composing after both hold suffixes
  # (#425).  Suffix names the KWINTRIM SETTING, not the per-corner resolved
  # code -- rationale at window_trim_tag_suffix().
  tag="${tag}$(window_trim_tag_suffix)"
  tag=$(simenv_mktag "${tag}")
  rundir="${WORK}/${tag}"; log="${rundir}/ngspice.log"
  libs="$(libs_for "${bundle}")"

  # Snap every phase probe onto a reference HALF-period, tstart + (k+0.5)/f_ref
  # with tstart = 0.5/f_ref, so REF and FB rises paired by a probe are the same
  # cycle's and the measurement cannot alias by a whole reference period.
  snap() { awk -v t="$1" -v f="${KFREF}" \
    'BEGIN{ tr=1/f; ts=0.5*tr; k=int((t-ts)/tr - 0.5 + 0.5); if(k<0)k=0;
            printf "%.12g", ts + (k+0.5)*tr }'; }
  # Seconds, from a "<n><u|n|p>" literal -- the same suffix alphabet run.sh's
  # own KD_*/KTA_* constants use.  A bare number passes through unchanged.
  sec() { case "$1" in
    *u) awk -v x="${1%u}" 'BEGIN{printf "%.12g", x*1e-6}' ;;
    *n) awk -v x="${1%n}" 'BEGIN{printf "%.12g", x*1e-9}' ;;
    *p) awk -v x="${1%p}" 'BEGIN{printf "%.12g", x*1e-12}' ;;
    *)  printf '%s' "$1" ;;
  esac; }
  addoff() { awk -v a="$1" -v d="$2" 'BEGIN{printf "%.12g", a+d}'; }
  t_step_s="$(sec "${KD_TSTEP}")"
  t_ramp_s="$(sec "${KD_TRAMP}")"
  t_rend_s="$(sec "${KD_TREND}")"
  t_stop_s="$(sec "${KD_TSTOP}")"
  ta_hi_s="$(sec "${KD_TA_HI}")"
  tb_hi_s="$(sec "${KD_TB_HI}")"
  # p1..p12, each an OFFSET from the phase of the profile it belongs to --
  # p1/p2 (pre-step) and p3..p6 (through the step) fixed relative to t_step;
  # p7/p8 the high-plateau window, stated directly as KD_TA_HI/KD_TB_HI so the
  # escalated run can push it far later without disturbing the others; p9..p12
  # (ramp and end plateau) relative to t_ramp/t_rend/tstop, so pushing the
  # high-plateau hold out for an escalated run carries the ramp and the end
  # plateau out with it rather than compressing them; p11/p12 additionally
  # overridable outright (KD_P11/KD_P12) so the END-plateau escalation can
  # push the post-ramp window past a tstop the derived form would peg it to
  # (#255).  Reduces to the exact literal probe times this deck has always
  # used (2.4e-6 .. 28.8e-6) at the unoverridden defaults.
  p11_s="$(sec "${KD_P11:-$(addoff "${t_rend_s}" 1.6e-6)}")"
  p12_s="$(sec "${KD_P12:-$(addoff "${t_stop_s}" -1.6e-6)}")"
  P=()
  for t in 2.4e-6 4.0e-6 \
           "$(addoff "${t_step_s}" 0.32e-6)" "$(addoff "${t_step_s}" 1.12e-6)" \
           "$(addoff "${t_step_s}" 2.4e-6)"  "$(addoff "${t_step_s}" 5.6e-6)" \
           "${ta_hi_s}" "${tb_hi_s}" \
           "$(addoff "${t_ramp_s}" 2.4e-6)" "$(addoff "${t_rend_s}" -0.8e-6)" \
           "${p11_s}" "${p12_s}"; do
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
  params+=( $(cloop_window_trim_params "$(window_trim_code_of "${bundle}")") )
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
  # Escalation rank (0 default hold, 1 escalated to the longer high-plateau
  # hold) and the high-plateau window's END instant KD_TB_HI -- the pair
  # report.sh needs to state, per corner, which hold length criterion 3's
  # verdict was measured at (mirroring --one-lock's trailing tstop/tmax
  # fields for the criterion-1 escalation, #253).
  esc_rank=0; [ "${KD_TRAMP}" = "${KD_TRAMP_BASE}" ] || esc_rank=1
  # The same pair again for the END plateau (#255): rank, and the instant the
  # ferr_end/lock_end/vc_end window for THIS row actually ended at (p12, in
  # seconds).  Two independent ranks rather than one, because a corner can be
  # escalated on either plateau, on both, or on neither, and collapsing that
  # into a single number would lose which measurement the row is good for.
  # APPENDED, never inserted: every awk block downstream reads the fixed
  # fields $5..$48 by position.
  esc_rank_end=0; [ -z "${KD_P12}" ] || esc_rank_end=1
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
    # Both instants are emitted in SECONDS -- the snapped probe times p8 and
    # p12 the deck was actually run with, not the "14.4u"-style literal the
    # constant is written as.  report.sh scales these by 1e6 to print
    # microseconds, and a suffixed literal would silently read as 14.4 there.
    printf ',%s,%s,%s,%s\n' "${esc_rank}" "${P[7]}" "${esc_rank_end}" "${P[11]}"
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

  # --- per-REF-cycle phase trace (#395) --------------------------------------
  # The decimated trace above answers "did LOCK come back", because LOCK is a
  # flag with microsecond-scale dynamics that a 20 ns decimation resolves.  It
  # cannot answer "how is the REF->FB phase decaying", because that quantity is
  # a few NANOSECONDS of edge-to-edge skew: a decimated sample of v(fb) does
  # not carry it at all.  Before #395 the only phase this deck reported was the
  # twelve `phi01..phi12` point samples, of which exactly TWO (phi07/phi08) sit
  # on the high plateau -- and DR-011 Decision 2 declined to turn the resulting
  # post-step settling bracket into a `spec/pll.md` bound precisely because two
  # samples cannot distinguish a single-pole decay from an under-damped one.
  #
  # So the phase is extracted here, once per REFERENCE CYCLE, over the WHOLE
  # profile, from the same full-resolution trace the decimation above reads:
  #
  #   - the crossing instants are found by LINEAR INTERPOLATION between the two
  #     adjacent ngspice samples that straddle the threshold.  That is the one
  #     place this file interpolates, and it is unavoidable -- an edge crossing
  #     is by definition between samples.  The error is bounded by the sample
  #     spacing on the edge, which the closed-loop timestep ceiling caps at
  #     ${KTMAX} (sim/README.md's "Closed-loop internal-timestep bound"), two
  #     orders of magnitude below the nanosecond-scale quantity being measured;
  #   - the threshold is `v_lo/2`, the SAME threshold `tb_supply_dyn.sp`'s own
  #     `.meas phi01..phi12` use, on both REF and FB.  It has to be the same
  #     one or the trace would not be comparable with the point samples;
  #   - each REF rise is paired with the NEAREST FB rise, and the pair is
  #     emitted only when |phi| < half a reference period.  That reproduces the
  #     `.meas ... trig v(ref) ... targ v(fb) ...` pairing (whose probe instants
  #     `snap()` deliberately places on a reference HALF-period so the two
  #     edges a probe pairs are the same cycle's) and makes the aliasing
  #     failure it guards against detectable rather than silent: a cycle whose
  #     phase leaves that window is DROPPED from the trace, not folded into it.
  #
  # The cross-check that this extraction is right is free and is in the record:
  # the deck's own `phi07`/`phi08` are measured at instants this trace also
  # covers, so the two must agree to interpolation error.  A discrepancy means
  # the extraction is wrong, and says so before any decay law is fitted.
  {
    echo "# gf180-pll :: supply-sensitivity :: per-REF-cycle REF->FB phase trace"
    echo "# corner: ${bundle} / ${temp} C, band ${band}, N=${KN}, f_ref=${KFREF} Hz"
    echo "# profile: ${KD_LO} V -> step(${KD_TEDGE}) -> ${KD_HI} V @ ${KD_TSTEP};"
    echo "#          ramp ${KD_TRAMP}..${KD_TREND} -> ${KD_END} V; hold to ${KD_TSTOP}"
    echo "# threshold: v_lo/2 = $(awk -v v="${KD_LO}" 'BEGIN{printf "%.6g", v/2}') V on BOTH v(ref) and v(fb) -- the same"
    echo "#          threshold tb_supply_dyn.sp's own .meas phi01..phi12 use"
    echo "# t_ref_s:  the interpolated v(ref) rising crossing, one row per reference cycle"
    echo "# phi_ns:   (nearest v(fb) rising crossing) - t_ref_s, in ns; positive = FB LAGS REF"
    echo "#          rows whose |phi| reaches half a reference period are DROPPED, not folded"
    echo "# lock_v / vctrl_v / vdd_v: the ngspice sample at the crossing, un-interpolated"
    echo "t_ref_s,phi_ns,lock_v,vctrl_v,vdd_v"
    # phase_trace.awk (#395) -- extracted to its own file so it can be
    # unit-tested against a synthetic trace (testbench/tests/) without a
    # multi-hour ngspice run.  Behaviour is unchanged from before extraction.
    awk -v vth="$(awk -v v="${KD_LO}" 'BEGIN{printf "%.12g", v/2}')" \
        -v halfT="$(awk -v f="${KFREF}" 'BEGIN{printf "%.12g", 0.5/f}')" \
        -f "${HERE}/phase_trace.awk" "${rundir}/supply_transient_full.csv"
  } >"${wave%.csv}_phase.csv"
  exit 0
fi

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
simenv_require_tools
# Opt in to sim/lib/simenv.sh's ngspice-internal-threading pin (#241): this
# campaign is the one that originally surfaced the self-oversubscription
# failure mode in #58 (SIM_JOBS=6 external processes x an OpenMP-linked
# ngspice's own internal threads squared the host's thread count, measured
# ~55x wall-clock regression) but had not adopted #146's per-campaign fix.
# A no-op on a host/build where ngspice is not internally threaded, and never
# overrides an OMP_NUM_THREADS/OMP_THREAD_LIMIT the caller already set.
#
# #242/#244: on this campaign's closed-loop lock deck, `OMP_NUM_THREADS`
# alone was found NOT to reduce ngspice's live thread count (unlike #146's
# charge-pump-only deck) -- `simenv_apply_omp_pin` now also exports
# `OMP_THREAD_LIMIT`, the variable #244 found actually caps this deck's
# thread count; see sim/supply-sensitivity/records/20260829-114117-aca2990.md.
simenv_apply_omp_pin
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
  in_grid "${bundle}" "${temp}" || continue
  if [ "${band}" = "-1" ]; then
    NOBAND="${NOBAND}${bundle}/${temp}C "
    continue
  fi
  emit_pre "${bundle}" "${temp}" "${band}" "${v297}" "${v330}" "${v363}" "${KFOUT}" "${KFREF}" 100
done <"${OPTAB}"
while IFS=, read -r bundle temp band v297 v330 v363; do
  in_list "${bundle}" "${SPLIT_BUNDLES}" || continue
  in_list "${temp}"   "${SPLIT_TEMPS}"   || continue
  in_grid "${bundle}" "${temp}"          || continue
  [ "${band}" = "-1" ] && continue
  emit_pre "${bundle}" "${temp}" "${band}" "${v297}" "${v330}" "${v363}" "${KFOUT2}" "${KFREF2}" 050
done <"${OPTAB2}"

NPRE=$(wc -l <"${JOBSPRE}" | tr -d ' ')
echo "supply-sensitivity: ${NPRE} in-loop control-voltage calibration runs (2 forced points each)"
# Refuse a multi-unit local grid on a batch-backend host (#740).
simenv_guard_local_grid "${NPRE}" "supply-sensitivity" || exit $?
# shellcheck disable=SC2016
xargs -P "$(simenv_jobs)" -L 1 \
  "${BASH:-/bin/bash}" -c 'exec "$0" --one-vpre "$@"' "${HERE}/run.sh" <"${JOBSPRE}"

vpre_of() {  # <slug> <bundle> <temp> <vdd> -> calibrated control voltage
  # "The pre-pass did not calibrate this point" is a LEGITIMATE state, not an
  # error, and it has to come back as an empty answer with a zero status.
  # Both callers below already handle empty -- the steady grid fails with a
  # message that names the point, the step/ramp list skips the corner -- but
  # neither ever got the chance: with the file missing, `awk` exited 2, and a
  # command substitution's status is the assignment's status, so `set -e`
  # killed the whole campaign right there.  No message, no record, exit 2,
  # after the pre-pass had already been paid for.
  #
  # Reachable as soon as SIM_PICKS (#411/PR #418) is used: the picks narrow
  # which points the pre-pass calibrates, DYN_PICKS defaults to `typical 27`
  # independently of them, and any pick set not containing `typical 27` leaves
  # the step/ramp corner uncalibrated.  #417's two-cell run is exactly that
  # shape and is where this was found.
  local f="${WORK}/vpre_$1_$2_$3_$4.txt"
  [ -f "${f}" ] || return 0
  awk '{print $1}' "${f}" 2>/dev/null
}

# --- job list: the steady-state grid at 100 MHz -----------------------------
JOBS100="${WORK}/jobs_100.txt"; : >"${JOBS100}"
while IFS=, read -r bundle temp band v297 v330 v363; do
  in_grid "${bundle}" "${temp}" || continue
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
  in_grid "${bundle}" "${temp}"          || continue
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
  # Skipping is correct -- the step/ramp deck needs this corner's calibrated
  # warm start and there is none -- but it must be VISIBLE.  Criterion 3 then
  # reports as NOT MEASURED in the record, and a reader who expected a
  # step/ramp result is entitled to know which corner dropped out and why
  # rather than inferring it from a zero.
  if [ -z "${v330}" ] || [ "${v330}" = "nan" ]; then
    echo "supply-sensitivity: step/ramp corner ${b}/${t}C skipped -- no calibrated" \
         "Vctrl at 3.30 V (not in this run's SIM_PICKS/SIM_BUNDLES x SIM_TEMPS grid)" >&2
    continue
  fi
  echo "${b} ${t} ${band} ${v330} ${WORK}/sdyn_${b}_${t}.csv ${WORK}/wave_${b}_${t}.csv" >>"${JOBSDYN}"
done

N100=$(wc -l <"${JOBS100}" | tr -d ' ')
N050=$(wc -l <"${JOBS050}" | tr -d ' ')
NDYN=$(wc -l <"${JOBSDYN}" | tr -d ' ')
echo "supply-sensitivity: ${N100} steady-state runs @ ${KFOUT} Hz, ${N050} @ ${KFOUT2} Hz (power split), ${NDYN} step/ramp runs; $(simenv_jobs) parallel jobs"
[ -z "${NOBAND}" ] || echo "supply-sensitivity: NO single band spans +/-10 % at: ${NOBAND}"
# Refuse a multi-unit local grid on a batch-backend host (#740).
simenv_guard_local_grid "$(( N100 + N050 + NDYN ))" "supply-sensitivity" || exit $?

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
# TWO GATES, NOT ONE (#394).  Until #394 the only gate was `|ferr| > ACC_FERR`,
# and that gate is blind to exactly the failure it exists to prevent: the
# PHASE criterion is judged from a single sample at `tb`, and nothing checked
# whether the phase was still moving when that sample was taken.  Record
# `20260901-155456-46b92f8` reported 1.796 ns of "static" phase at
# `ff`/125 C/3.63 V -- 1.8x the ratified criterion, and the number #394 was
# filed about -- from a run whose `ferr` was 2.255e-4, comfortably INSIDE
# ACC_FERR, so the corner was never escalated. Inverting the deck's own
# `ferr = -(phi_b - phi_a)/(tb - ta)` identity shows that phase had moved from
# 2.518 ns to 1.796 ns across the late window and was still falling: a sample
# on a tail, reported as a design result. 30 of that grid's 45 rows are in the
# same state, and 15 of its 17 rows over the ratified bound.
#
# So a corner is now escalated when EITHER
#
#   (a) |ferr| > ACC_FERR                    -- still converging in FREQUENCY
#   (b) |phi_b - phi_a| > ACC_PHI_SETTLE_S   -- still converging in PHASE
#
# where (b) is computed from the same two committed columns, |ferr| * (tb - ta),
# with no new measurement and no model.  The two gates are independent: (a) can
# pass while (b) fails, which is precisely the `ff`/125 C/3.63 V case, and the
# whole point of adding it.  Gate (b) is not a stricter (a): a small residual
# frequency error integrated over a long late window is a large phase shift,
# and it is the phase that the criterion bounds.
#
# Corners are ordered for escalation by how far each is from settled on the
# gate that fired, normalised to that gate's own threshold, so a compute cap
# (SIM_EXTEND_MAX) takes the worst offenders whichever gate they tripped
# rather than always preferring frequency ones.
#
#   SIM_EXTEND=off        skip the escalation entirely
#   SIM_EXTEND_TSTOP/_TA/_TB   the longer transient (default 36.8u/31.2u/34.4u)
#   SIM_EXTEND_MAX=<n>    cap the number of escalated corners (compute budget);
#                         the worst residuals are escalated first, and
#                         report.sh states the cap in the record when it bites.
JOBS100X="${WORK}/jobs_100x.txt"; : >"${JOBS100X}"
# The late window in seconds, from KTA/KTB's own "<n><u|n|p>" literals.  Gate
# (b) needs it because the CSV carries the phase SLIP RATE (`ferr`), not the
# phase shift, and the shift is what the criterion is about.
KWIN_S="$(awk -v a="${KTA}" -v b="${KTB}" '
  function s(x,  n) { n = x + 0;
    if (x ~ /u$/) return n * 1e-6;
    if (x ~ /n$/) return n * 1e-9;
    if (x ~ /p$/) return n * 1e-12;
    return n }
  BEGIN { printf "%.12g", s(b) - s(a) }')"
if [ "${SIM_EXTEND:-auto}" != "off" ]; then
  cat "${WORK}"/s100_*.csv 2>/dev/null | awk -F, -v accf="${ACC_FERR}" -v w="${WORK}" \
      -v accps="${ACC_PHI_SETTLE_S}" -v win="${KWIN_S}" \
      -v fo="${KFOUT}" -v fr="${KFREF}" '
    { fe = $13 + 0; if (fe < 0) fe = -fe;
      # How far the phase moved across the late window, from the definition of
      # ferr itself: a residual frequency error slips the phase at exactly
      # df/f seconds per second, so the shift is |ferr| * (tb - ta).
      dphi = fe * win;
      # Distance from settled on each gate, in units of that gate threshold, so
      # one sort key ranks both populations comparably under SIM_EXTEND_MAX.
      rf = (accf  > 0) ? fe   / accf  : 0;
      rp = (accps > 0) ? dphi / accps : 0;
      r  = (rf > rp) ? rf : rp;
      if (fe > accf || dphi > accps)
        printf "%.6g %s %s %s %s %s %s %s %s/s100x_%s_%s_%s.csv\n",
          r, $1, $2, $3, $5, $9, fo, fr, w, $1, $2, $3 }' \
    | sort -rn | cut -d' ' -f2- \
    | { if [ -n "${SIM_EXTEND_MAX:-}" ]; then head -n "${SIM_EXTEND_MAX}"; else cat; fi } \
    >"${JOBS100X}"
fi
NX=$(wc -l <"${JOBS100X}" | tr -d ' ')
if [ "${NX}" -gt 0 ]; then
  # Refuse a multi-unit local grid on a batch-backend host (#740).
  simenv_guard_local_grid "${NX}" "supply-sensitivity" || exit $?
  echo "supply-sensitivity: ${NX} corner(s) not settled in frequency or phase at ${KTSTOP} -- re-running at ${KTSTOP_X}"
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
  # Refuse a multi-unit local grid on a batch-backend host (#740).
  simenv_guard_local_grid "${NM}" "supply-sensitivity" || exit $?
  echo "supply-sensitivity: ${NM} corner(s) still over ${ACC_FERR} at ${KTSTOP_X} -- re-running at timestep ceiling ${KTMAX_X}"
  # shellcheck disable=SC2016
  SIM_TSTOP="${KTSTOP_X}" SIM_TA="${KTA_X}" SIM_TB="${KTB_X}" SIM_TMAX="${KTMAX_X}" \
    xargs -P "$(simenv_jobs)" -L 1 \
      "${BASH:-/bin/bash}" -c 'exec "$0" --one-lock "$@"' "${HERE}/run.sh" <"${JOBS100M}"
fi

wait "${DYNPID}"

# --- criterion-3 high-plateau settling escalation (#253) --------------------
# A step/ramp corner whose measured ferr_hi (the residual frequency error on
# the HIGH plateau, after the step) exceeds ACC_FERR at the default
# ${KD_TB_HI} window has not been shown to fail the stays-locked criterion --
# it has been shown to still be settling after the step, and at LESS settling
# time than criterion 1's own default window gets (see the KD_TA_HI_X/
# KD_TB_HI_X derivation above).  So it is re-run with the high-plateau hold
# pushed out to KD_TB_HI_X before the ramp resumes, mirroring the criterion-1
# escalation immediately above: mechanism, not a note asking someone to
# re-run it by hand.
#
#   SIM_DYN_EXTEND=off                 skip this escalation entirely
#   SIM_DYN_EXTEND_TA/_TB/_TRAMP/_TREND/_TSTOP   the longer profile
#   SIM_DYN_EXTEND_MAX=<n>              cap the number of escalated corners
JOBSDYNX="${WORK}/jobs_dynx.txt"; : >"${JOBSDYNX}"
if [ "${SIM_DYN_EXTEND:-auto}" != "off" ]; then
  cat "${WORK}"/sdyn_*.csv 2>/dev/null | awk -F, -v accf="${ACC_FERR}" -v w="${WORK}" '
    { fe = $18 + 0; if (fe < 0) fe = -fe;
      if (fe > accf) printf "%.6g %s %s %s %s %s/sdynx_%s_%s.csv %s/wavex_%s_%s.csv\n",
        fe, $1, $2, $3, $4, w, $1, $2, w, $1, $2 }' \
    | sort -rn | cut -d' ' -f2- \
    | { if [ -n "${SIM_DYN_EXTEND_MAX:-}" ]; then head -n "${SIM_DYN_EXTEND_MAX}"; else cat; fi } \
    >"${JOBSDYNX}"
fi
NDX=$(wc -l <"${JOBSDYNX}" | tr -d ' ')
if [ "${NDX}" -gt 0 ]; then
  # Refuse a multi-unit local grid on a batch-backend host (#740).
  simenv_guard_local_grid "${NDX}" "supply-sensitivity" || exit $?
  echo "supply-sensitivity: ${NDX} corner(s) missed the high-plateau lock criterion at ${KD_TB_HI} -- re-running with the hold pushed to ${KD_TB_HI_X}"
  # shellcheck disable=SC2016
  SIM_DYN_TA_HI="${KD_TA_HI_X}" SIM_DYN_TB_HI="${KD_TB_HI_X}" \
    SIM_DYN_TRAMP="${KD_TRAMP_X}" SIM_DYN_TREND="${KD_TREND_X}" SIM_DYN_TSTOP="${KD_TSTOP_X}" \
    xargs -P "$(simenv_jobs)" -L 1 \
      "${BASH:-/bin/bash}" -c 'exec "$0" --one-dyn "$@"' "${HERE}/run.sh" <"${JOBSDYNX}"
fi

# --- criterion-3 END-plateau settling escalation (#255) ---------------------
# The same mechanism again, one plateau later: a corner whose |ferr_end| (the
# residual frequency error on the END plateau, after the RAMP) exceeds
# ACC_FERR at the default 8.0 us post-ramp hold has not been shown to fail the
# stays-locked criterion, only to still be converging after the ramp.  So it
# is re-run with p11/p12 and tstop pushed out by KD_DEND_TA/_TB/_TSTOP from
# ITS OWN t_rend.
#
# This runs AFTER the high-plateau escalation, not beside it, and reads the
# BEST-so-far row per corner (the #253-escalated run where one exists, else
# the default-hold run).  That is what makes the two escalations COMPOSE
# rather than compete: a corner that missed both plateaus is re-run on the
# high-plateau-escalated profile with the post-ramp hold extended on top, so
# exactly one row per corner is the best-resolved one on both plateaus at
# once and report.sh's "longest hold wins" rule stays a total order.  The two
# job lists below are that split -- same escalation, two different base
# profiles, so each batch has to carry its own instants.
#
#   SIM_DYN_END_EXTEND=off             skip this escalation entirely
#   SIM_DYN_END_TA/_TB/_TSTOP          the post-ramp offsets it escalates to
#   SIM_DYN_END_MAX=<n>                cap the number of escalated corners;
#                                      worst |ferr_end| first
JOBSDEND="${WORK}/jobs_dend.txt";   : >"${JOBSDEND}"
JOBSDENDX="${WORK}/jobs_dendx.txt"; : >"${JOBSDENDX}"
if [ "${SIM_DYN_END_EXTEND:-auto}" != "off" ]; then
  JOBSDENDALL="${WORK}/jobs_dend_all.txt"
  { cat "${WORK}"/sdyn_*.csv 2>/dev/null; cat "${WORK}"/sdynx_*.csv 2>/dev/null; } \
    | awk -F, '
        { k = $1 "|" $2; r = $49 + 0;
          if (!(k in br) || r > br[k]) { br[k] = r; best[k] = $0 } }
        END { for (k in best) print best[k] }' \
    | awk -F, -v accf="${ACC_FERR}" -v w="${WORK}" '
        { fe = $19 + 0; if (fe < 0) fe = -fe;
          if (fe > accf) printf "%d %.6g %s %s %s %s %s/sdynend_%s_%s.csv %s/waveend_%s_%s.csv\n",
            $49 + 0, fe, $1, $2, $3, $4, w, $1, $2, w, $1, $2 }' \
    | sort -k2,2gr \
    | { if [ -n "${SIM_DYN_END_MAX:-}" ]; then head -n "${SIM_DYN_END_MAX}"; else cat; fi } \
    >"${JOBSDENDALL}"
  awk '$1 == 0' "${JOBSDENDALL}" | cut -d' ' -f3- >"${JOBSDEND}"
  awk '$1 == 1' "${JOBSDENDALL}" | cut -d' ' -f3- >"${JOBSDENDX}"
fi
# t_rend + offset, in seconds, from two "<n><u|n|p>"-suffixed literals -- the
# top-level twin of --one-dyn's own sec()/addoff() pair. simenv_dend_at()
# (sim/lib/simenv.sh) is the shared implementation; report.sh re-derives the
# same instants with the same helper (#329).
NDE=$(( $(wc -l <"${JOBSDEND}" | tr -d ' ') + $(wc -l <"${JOBSDENDX}" | tr -d ' ') ))
# Refuse a multi-unit local grid on a batch-backend host (#740).
simenv_guard_local_grid "${NDE}" "supply-sensitivity" || exit $?
if [ -s "${JOBSDEND}" ]; then
  echo "supply-sensitivity: $(wc -l <"${JOBSDEND}" | tr -d ' ') corner(s) still converging on the END plateau at ${KD_TSTOP_BASE} -- re-running at $(simenv_dend_at "${KD_TREND_BASE}" "${KD_DEND_TSTOP}") s"
  # shellcheck disable=SC2016
  SIM_DYN_P11="$(simenv_dend_at "${KD_TREND_BASE}" "${KD_DEND_TA}")" \
    SIM_DYN_P12="$(simenv_dend_at "${KD_TREND_BASE}" "${KD_DEND_TB}")" \
    SIM_DYN_TSTOP="$(simenv_dend_at "${KD_TREND_BASE}" "${KD_DEND_TSTOP}")" \
    xargs -P "$(simenv_jobs)" -L 1 \
      "${BASH:-/bin/bash}" -c 'exec "$0" --one-dyn "$@"' "${HERE}/run.sh" <"${JOBSDEND}"
fi
if [ -s "${JOBSDENDX}" ]; then
  echo "supply-sensitivity: $(wc -l <"${JOBSDENDX}" | tr -d ' ') high-plateau-escalated corner(s) still converging on the END plateau -- re-running at $(simenv_dend_at "${KD_TREND_X}" "${KD_DEND_TSTOP}") s"
  # shellcheck disable=SC2016
  SIM_DYN_TA_HI="${KD_TA_HI_X}" SIM_DYN_TB_HI="${KD_TB_HI_X}" \
    SIM_DYN_TRAMP="${KD_TRAMP_X}" SIM_DYN_TREND="${KD_TREND_X}" \
    SIM_DYN_P11="$(simenv_dend_at "${KD_TREND_X}" "${KD_DEND_TA}")" \
    SIM_DYN_P12="$(simenv_dend_at "${KD_TREND_X}" "${KD_DEND_TB}")" \
    SIM_DYN_TSTOP="$(simenv_dend_at "${KD_TREND_X}" "${KD_DEND_TSTOP}")" \
    xargs -P "$(simenv_jobs)" -L 1 \
      "${BASH:-/bin/bash}" -c 'exec "$0" --one-dyn "$@"' "${HERE}/run.sh" <"${JOBSDENDX}"
fi

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
gotdynx=$(cat "${WORK}"/sdynx_*.csv 2>/dev/null | wc -l | tr -d ' ')
[ "${gotdynx}" -eq "${NDX}" ] || { echo "ERROR: expected ${NDX} high-plateau settling re-run rows, got ${gotdynx}" >&2; exit 1; }
gotdynend=$(cat "${WORK}"/sdynend_*.csv 2>/dev/null | wc -l | tr -d ' ')
[ "${gotdynend}" -eq "${NDE}" ] || { echo "ERROR: expected ${NDE} END-plateau settling re-run rows, got ${gotdynend}" >&2; exit 1; }

exec "${HERE}/report.sh" "${WORK}" "${EXP}" "${HERE}"
