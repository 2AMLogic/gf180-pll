#!/usr/bin/env bash
# gf180-pll :: vco-tuning-range :: VCO band-select mirror Monte Carlo (#146)
#
# Characterizes the frequency DISPERSION random device mismatch in the
# band-select mirror (design/README.md's "3-bit band-select mirror" --
# design/vco_bias.sch's cascaded current mirrors) adds on top of the
# systematic f(Vctrl)/band-plan curve testbench/tb.json's harness-driven
# sweep already measures (sw_stat_mismatch=0 there, unchanged). This is a
# SEPARATE, additive record, not a re-run of that sweep with the switch
# flipped -- see below for why.
#
# --- Why a raw sim/lib/simenv.sh deck instead of extending tb.json --------
#
# The obvious-looking approach -- add `"params": {"sw_stat_mismatch": "1"}`
# to testbench/tb.json -- was tried first and found NOT to work, for a
# harness-ordering reason worth recording so the next person does not
# rediscover it the hard way:
#
#   sim/harness/runner.py's compose_deck() emits every `tb.params` entry as a
#   `.param key=value` line BEFORE `.include "<design.ngspice>"` (see that
#   file: the PVT-parameter block at the top of the generated deck, then the
#   models section). design.ngspice itself declares
#   `.param sw_stat_global = 0` / `.param sw_stat_mismatch = 0` -- AFTER the
#   testbench's own params, in deck order. Direct experiment (three ngspice
#   decks, redefinition ordering isolated from every other variable) confirms
#   ngspice-46 resolves a parameter redefined more than once by LAST
#   occurrence in the deck, not first -- so a tb.json `params` override of
#   sw_stat_mismatch is SILENTLY nullified back to design.ngspice's own
#   default by the include that follows it. This is a genuine, previously
#   undocumented harness limitation (it affects ANY manifest trying to
#   override a design.ngspice-defaulted global via `params`, not just this
#   one) -- fixing it generally is out of scope for #146 (a shared
#   sim/harness/runner.py behavior change affecting every existing harness
#   campaign's deck ordering needs its own review, not a side effect of a
#   two-record evidence issue) and is worth a follow-up issue if the operator
#   agrees.
#
#   sim/mc-cp-mismatch's own established pattern already puts the override
#   AFTER the design.ngspice include (simenv_run_deck emits `.param` kv
#   overrides, then `.include "<campaign deck>"` last) -- which is exactly
#   why that campaign's `sw_stat_mismatch=1` override works. This deck
#   reuses the SAME ordering by declaring the switches directly inside
#   tb_vco_mismatch.sp (included after the corner .lib sections, same as
#   every other testbench netlist in this repo), not via a `params` kv.
#
#   Separately, the harness's PVT-grid runner has no Monte Carlo seed axis:
#   `.option rndseed=N` must be read at netlist PARSE time (see
#   sim/mc-cp-mismatch's established finding, confirmed unchanged by this
#   issue), and neither tb.json's `sweeps` axis mechanism nor its `options`
#   list passes a per-point value through the harness's `{placeholder}`
#   substitution the way `analyses` text does -- so a seed axis would need
#   its own harness feature, not just a manifest edit.
#
# Given both gaps, this campaign reuses mc-cp-mismatch's raw
# `sim/lib/simenv.sh` pattern (the same pattern that campaign itself uses
# because it predates the harness) instead of "extending" the harness
# manifest that does not yet support either need. testbench/tb.json's own
# harness-driven sweep is UNCHANGED by this file (still sw_stat_mismatch=0,
# still the systematic PVT claim) -- this is additive, not a replacement.
#
# --- Scope of this campaign -------------------------------------------------
#
# ONE VCO copy (not the seven-copy f(Vctrl) topology) at a FIXED Vctrl
# (1.8 V, mid-window) and TWO band codes -- band 0 (no switched leg active:
# only the three always-on mirror legs) and band 7 (every switched leg
# active: the full three-cascade path) -- the two ends of the band-select
# mirror's cascade activation, at nominal PVT
# (typical/27C/3.30V). sim/README.md's "single nominal point ... for a Monte
# Carlo distribution claim ... allowed with justification" rule applies here
# exactly as it does for mc-cp-mismatch: corner sensitivity of the MEAN is
# testbench/tb.json's job (45-corner grid, already measured); this
# campaign's job is the DISPERSION mismatch adds on top, and there is no
# reason to expect the mirror's Pelgrom-mismatch mechanism to have strong PVT
# dependence the way a systematic tail-charge term would (same reasoning
# mc-cp-mismatch's original nominal-only record used). #146's
# mc-cp-mismatch corner-grid extension (this issue's other half) is where
# that assumption gets its own combined-with-corners check for the
# charge-pump/PFD side of the loop; this smaller campaign does not repeat
# that exercise for the VCO given the added wall clock a second corner-grid
# extension would cost in the same PR.
#
# No numeric budget exists for VCO band-select mirror mismatch in
# design/README.md (only the charge-pump "Up/down mismatch budget" table
# does) -- this record reports the measured dispersion without a pass/fail
# verdict, same honest handling mc-cp-mismatch already uses for its
# divider-retiming-flop term (also not itself a budget-table line).
#
# --- Erratum: the `# switches:` line of the CSV already committed (#601) -----
#
# Until #601 `simenv_provenance` hardcoded one switches line for every CSV it
# headed, with no parameter and no condition --
#
#   # switches: design.ngspice defaults (sw_stat_global=0, sw_stat_mismatch=0
#   #           -> nominal skew, no Monte Carlo)
#
# -- which is the opposite of what tb_vco_mismatch.sp does (it declares
# sw_stat_global=0 / sw_stat_mismatch=1 after the design.ngspice include,
# specifically so the later declaration wins; see the harness-ordering finding
# above). The record's Environment provenance field has stated that correctly
# all along, because simenv_env_block took the override parameter and
# simenv_provenance did not. One committed CSV shipped with the wrong header:
#
#   corners/20260817-143524-0e9cfc9/mismatch.csv
#
# The negative control (#602, added below) joined this list rather than
# escaping it: its own `simenv_provenance` call was written and merged before
# this erratum's pairing rule (sim/tests/test_provenance_switches_note.py)
# could see through the `mc_mismatch`-handle indirection the control needed
# and flag it as a mismatch-on call missing its fifth argument. One more file,
# minted before ITS fix:
#
#   corners/20260927-094524-b994116/negative_control.csv
#
# Those bytes are NOT edited and neither are the records beside them -- `sim/`
# is append-only evidence and sim/README.md forbids rewriting a committed
# record even to add a true, helpful pointer. The correction is made forward,
# here in the live testbench artifact, the same disposition
# sim/lock-window-trim/testbench/tb.json uses for its own stale-figure erratum.
# For those two files the record's Environment provenance field (or, for the
# negative control, its own "read the column not the header" note) is
# authoritative and the CSV's `# switches:` line is a harness default that was
# never true of the run; every CSV minted from this script after its own fix
# states the switches the run actually used. sim/vco-tuning-range's OTHER
# committed CSVs (vco_tuning.csv, supply_jitter.csv, supply_pushing.csv,
# stage_count.csv) are correctly labelled -- mismatch really is off for those
# runs.
#
# Nothing computed is affected: no figure in any record, and no check script,
# parses that line -- simenv_datarows drops every `#` comment before the data
# is read.
#
# --- Negative control (#602) ------------------------------------------------
#
# This campaign used to have NO negative control of its own. Its records
# delegated item 6's "deterministic negative control" sub-criterion by
# citation -- "reuses the finding sim/mc-cp-mismatch/records/
# 20260731-212614-640560e.md established ... Not re-derived here" -- to a
# sibling campaign whose own control was, at the time, itself only prose.
# So the chain of evidence for this row ended in a sentence in a third
# record, two hops away, about a different DUT, a different deck and a
# different measurement. That is not a control for these samples.
#
# `--control` below gives this campaign one of its own, in the same shape and
# the same CSV schema as mc-cp-mismatch's (see sim/lib/simenv.sh's "Monte
# Carlo negative control" section for the three legs and why the `vary` leg
# matters), covering EVERY (corner, Vctrl, band) point the two Monte Carlo
# records under sim/vco-tuning-range/records/ actually sample -- including
# run_band0_worst_corner.sh's `ss`/125C/3.63V, Vctrl=2.7 V band-0 point,
# which shares this directory, this DUT and this deck. One control artifact
# per experiment directory, covering that directory's sampled points, rather
# than one per script.
#
# Usage:
#   ./run_mismatch.sh                 # full campaign -> mints a records/<id>.md
#   ./run_mismatch.sh --check         # 2 samples per band, to stdout
#   ./run_mismatch.sh --control       # the NEGATIVE CONTROL only (#602), all
#                                     # sampled (corner, Vctrl, band) points
#                                     # -> mints its own records/<id>.md +
#                                     # corners/<id>/negative_control.csv
#   ./run_mismatch.sh --recheck-control <id>
#                                     # re-derive a committed control's verdict
#                                     # from its CSV. Bytes only: no ngspice,
#                                     # no PDK. Non-zero exit if a leg fails.
#   SIM_JOBS=8 ./run_mismatch.sh      # cap parallelism
#   N_SAMPLES=.. ./run_mismatch.sh    # override per-band sample count

set -euo pipefail

# Host oversubscription fix, same finding as sim/mc-cp-mismatch/testbench/
# run.sh's #146 build (see that file's header comment for the full
# measurement): ngspice-46 on this repo's build host is compiled with
# OpenMP-parallel BSIM model evaluation, so every `ngspice -b` invocation
# spawns several OS threads on its own, independent of this script's own
# `xargs -P $(simenv_jobs)` process-level fan-out -- oversubscribing the
# host's 8 physical cores several times over from self-contention alone.
# Pinning one thread per ngspice process and letting `simenv_jobs` provide
# parallelism at the process level (measured ~44x wall-clock improvement on
# the sibling campaign) is the correct division for this host. #241
# centralized the DETECTION half of this fix into
# sim/lib/simenv.sh::simenv_apply_omp_pin -- called below, right after
# sourcing that file -- while keeping this campaign's own OPT-IN call (not a
# changed default inside simenv.sh itself). An explicit OMP_NUM_THREADS in
# the environment still always wins.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP="$(cd "${HERE}/.." && pwd)"
REPO="$(cd "${EXP}/../.." && pwd)"
# shellcheck source=../../lib/simenv.sh
. "${HERE}/../../lib/simenv.sh"
simenv_apply_omp_pin

DECK="${HERE}/tb_vco_mismatch.sp"
DUT_SRC="${REPO}/design/netlist/vco.spice"
WORK="${EXP}/work-mismatch"

# The VCO's frequency is set in part by a poly resistor (the V->I
# degeneration resistor and the constant-gm reference resistor) -- the MOS
# `typical` bundle alone omits the res_*/moscap_* passive sections, and this
# DUT's ppolyf_u_3k / cap_nmos_03v3 devices need them (same three-section
# bundle tb_vco_tuning.sp's pre-harness run.sh used via its `bundle_libs`
# helper -- see sim/README.md's "Default corner matrix" MOS-vs-passive-axis
# hazard note this DUT is a worked example of).
CORNER="typical,res_typical,moscap_typical"
CORNER_TAG=typical
TEMP=27
VDD=3.30
VCTRL=1.8

N_SAMPLES="${N_SAMPLES:-25}"

# Two band points: (band, b0, b1, b2, nominal-f-at-Vctrl=1.8V-typical-27C-3.30V,
# used only to size the transient window, per record
# sim/vco-tuning-range/records/20260804-164956-72883fb.md's raw_measures.csv
# f4 column -- never trusted for a result, only for tstep/tstop sizing, same
# convention as tb_vco_tuning.spice's calibrated-envelope comment). band0 =
# no switched leg active (always-on legs only); band7 = every switched leg
# active (full three-mirror cascade) -- the two ends of the band-select
# mirror's cascade activation.
BAND_POINTS=(
  "0 0 0 0 6526290"
  "7 1 1 1 261947000"
)

HEADER="band,seed,f_hz,i_a"

# The `# switches:` line of the CSV this script writes (#601), passed to
# simenv_provenance as its optional fifth argument. Prose counterpart: the
# simenv_env_block switches-note in the record body below. Without it
# simenv_provenance emits its design.ngspice-default wording, which for this
# deck says the opposite of what ran -- see the erratum in this file's header
# comment for the CSV that shipped that way.
SWITCHES_NOTE="design.ngspice defaults OVERRIDDEN by tb_vco_mismatch.sp, which re-declares them after the include (sw_stat_global=0, sw_stat_mismatch=1 -> mismatch-only Monte Carlo, .option rndseed set per sample)"

# The negative control (#602) deliberately runs BOTH switch values via the
# deck's mc_mismatch handle -- see its own comment above -- so neither
# SWITCHES_NOTE above nor the unmodified simenv_provenance default is honest
# for its CSV. Same #601 pairing rule, same enforcement (sim/tests/
# test_provenance_switches_note.py).
CONTROL_SWITCHES_NOTE="design.ngspice defaults OVERRIDDEN per run -- this control artifact runs BOTH switch values (sw_stat_mismatch=1 for the repeat/vary legs, OFF for the gate leg, via the deck's mc_mismatch handle); read the per-row sw_stat_mismatch column, not this line, for the authoritative per-run value"

stage_netlist() {
  mkdir -p "$1"
  cp "${DUT_SRC}" "$1/vco.spice"
}

# simenv_run_deck_retried (3-attempt retry wrapper around simenv_run_deck,
# #146 host-flakiness mitigation) is hoisted to sim/lib/simenv.sh -- #184.
# See that function's comment there for the full investigation.

# One (band, seed) sample -> one CSV row on stdout.
run_one() {
  local band="$1" b0="$2" b1="$3" b2="$4" fnom="$5" seed="$6" sfile="$7"
  local tag="band${band}_seed$(printf '%03d' "${seed}")"
  stage_netlist "${WORK}/${tag}"
  # Window sized generously off the nominal (mismatch-free) frequency: 30%
  # margin either side covers a mismatch-driven frequency shift far larger
  # than Vth/beta Pelgrom mismatch on gf180mcu 3.3V devices plausibly
  # produces (single-digit percent), so a missed .meas trigger here would
  # indicate a real problem worth seeing, not a tight window artifact.
  local flo fhi tsettle tstop tmax
  flo=$(awk -v f="${fnom}" 'BEGIN{print f*0.7}')
  fhi=$(awk -v f="${fnom}" 'BEGIN{print f*1.3}')
  tsettle=$(awk -v f="${flo}" 'BEGIN{printf "%.6g", 1.2*4/f}')
  tstop=$(awk -v ts="${tsettle}" -v f="${flo}" 'BEGIN{printf "%.6g", ts + 1.2*7/f}')
  tmax=$(awk -v f="${fhi}" 'BEGIN{printf "%.6g", 1/(80*f)}')
  simenv_run_deck_retried "${DECK}" "${WORK}" "${tag}" "${CORNER}" "${TEMP}" \
    "vsup=${VDD}" "vctrl=${VCTRL}" "b0v=$((b0))*${VDD}" "b1v=$((b1))*${VDD}" "b2v=$((b2))*${VDD}" \
    "tsettle=${tsettle}" "tstop=${tstop}" "tstep=${tmax}" "tmax=${tmax}" \
    "mc_mismatch=1" "rndseed=${seed}" >/dev/null
  local log="${WORK}/${tag}/ngspice.log" f i
  f=$(simenv_meas "${log}" f1)
  i=$(simenv_meas "${log}" i1)
  printf '%s,%s,%s,%s\n' "${band}" "${seed}" "${f}" "${i}" >>"${sfile}"
}

# ===========================================================================
# Negative control (#602) -- this campaign's own, not a citation
# ===========================================================================
#
# See this file's header comment for why this campaign previously had none,
# and sim/lib/simenv.sh's "Monte Carlo negative control" section for the
# three legs, the five run tags and the CSV schema. `mc_mismatch` is the
# handle the `gate` leg needs: tb_vco_mismatch.sp used to pin
# `sw_stat_mismatch=1` as a literal, which made a mismatch-OFF run of the
# same deck impossible (see that deck's own header note on the change).
CONTROL_SEED_A="${CONTROL_SEED_A:-1}"
CONTROL_SEED_B="${CONTROL_SEED_B:-97}"

# Every (corner, temperature, supply, Vctrl, band) point the Monte Carlo records
# in this experiment directory actually sample, with its own nominal-frequency
# window sizing -- the same constants those scripts use, not re-derived here:
#
#   stage | corner-libs | corner-tag | temp | vdd | vctrl | b0 b1 b2 | fnom |
#   win_lo | win_hi
#
# `stage` carries the Vctrl as well as the band because the SAME band appears at
# BOTH ends of the control window in the band-pair grid below (band 1 is the
# upper band of the B0 -> B1 pair at Vctrl = 0.9 V and the lower band of
# B1 -> B2 at 2.7 V). simenv_control_verdicts groups by (stage, corner), so a
# stage string that omitted Vctrl would silently merge those two points into one
# and report five runs where there are ten.
#
# `win_lo`/`win_hi` are the transient-window bracket, PER POINT, because the
# campaign's two sample paths do not use the same one: the single-band scripts
# use +/-30% and run_band_pair_worst_corner.sh uses 45%/45% (it has to hold a
# mismatched frequency whose 3-sigma spread is ~25% of the mean). A control run
# through a different transient than the samples it validates is not a control
# for those samples, so the bracket travels with the point rather than being a
# constant here.
#
# GROUPS:
#   (a) Points 1-2 are run_mismatch.sh's own (records/20260817-143524-0e9cfc9.md);
#       point 3 is run_band0_worst_corner.sh's
#       (records/20260923-084925-1655e11.md), whose FNOM_BAND0/corner/Vctrl
#       constants are copied from that script. These three are what #602's
#       original control covered.
#   (b) Points 4-25 (#622) are the two ends of every adjacent-band pair in
#       run_band_pair_worst_corner.sh's 11-point grid -- the widened sample grid
#       this control has to cover for signoff/README.md's "Item 6(c)" rule (a
#       control's grid is the grid of the samples it validates) to keep holding.
#       Each `fnom` is that script's own GRID row field for the same point, which
#       `run_band_pair_worst_corner.sh --grid` re-derives against
#       corners/20260804-164956-72883fb/raw_measures.csv with no simulator.
CONTROL_POINTS=(
  # (a) the three points #602's control already covered
  "band0_vc1.8 typical,res_typical,moscap_typical typical 27 3.30 1.8 0 0 0 6526290 0.7 1.3"
  "band7_vc1.8 typical,res_typical,moscap_typical typical 27 3.30 1.8 1 1 1 261947000 0.7 1.3"
  "band0_vc2.7 ss,res_typical,moscap_typical      ss      125 3.63 2.7 0 0 0 9122300 0.7 1.3"
  # (b1) the bundle axis -- B3 -> B4 at 125C/3.63V, all five MOS bundles
  "band3_vc2.7 typical,res_typical,moscap_typical typical 125 3.63 2.7 1 1 0 40223800 0.55 1.45"
  "band4_vc0.9 typical,res_typical,moscap_typical typical 125 3.63 0.9 0 0 1 30785300 0.55 1.45"
  "band3_vc2.7 ff,res_typical,moscap_typical      ff      125 3.63 2.7 1 1 0 39128100 0.55 1.45"
  "band4_vc0.9 ff,res_typical,moscap_typical      ff      125 3.63 0.9 0 0 1 29226700 0.55 1.45"
  "band3_vc2.7 fs,res_typical,moscap_typical      fs      125 3.63 2.7 1 1 0 41040100 0.55 1.45"
  "band4_vc0.9 fs,res_typical,moscap_typical      fs      125 3.63 0.9 0 0 1 30531400 0.55 1.45"
  "band3_vc2.7 sf,res_typical,moscap_typical      sf      125 3.63 2.7 1 1 0 39601500 0.55 1.45"
  "band4_vc0.9 sf,res_typical,moscap_typical      sf      125 3.63 0.9 0 0 1 31229800 0.55 1.45"
  "band3_vc2.7 ss,res_typical,moscap_typical      ss      125 3.63 2.7 1 1 0 41913500 0.55 1.45"
  "band4_vc0.9 ss,res_typical,moscap_typical      ss      125 3.63 0.9 0 0 1 33058900 0.55 1.45"
  # (b2) the temperature x supply box -- the other three vertices, ss, B3 -> B4
  "band3_vc2.7 ss,res_typical,moscap_typical      ss      -40 2.97 2.7 1 1 0 49967100 0.55 1.45"
  "band4_vc0.9 ss,res_typical,moscap_typical      ss      -40 2.97 0.9 0 0 1 35676900 0.55 1.45"
  "band3_vc2.7 ss,res_typical,moscap_typical      ss      -40 3.63 2.7 1 1 0 35705500 0.55 1.45"
  "band4_vc0.9 ss,res_typical,moscap_typical      ss      -40 3.63 0.9 0 0 1 26525300 0.55 1.45"
  "band3_vc2.7 ss,res_typical,moscap_typical      ss      125 2.97 2.7 1 1 0 57273800 0.55 1.45"
  "band4_vc0.9 ss,res_typical,moscap_typical      ss      125 2.97 0.9 0 0 1 43730500 0.55 1.45"
  # (b3) the pair axis at ss/125C/3.63V. band0_vc2.7 at this point is already
  # group (a)'s third row, at the +/-30% bracket the record that sampled it used;
  # the band-pair grid re-samples it at 45%/45%, so it appears again here under a
  # distinct stage rather than having its existing row's bracket rewritten.
  "band0_vc2.7_bp ss,res_typical,moscap_typical   ss      125 3.63 2.7 0 0 0 9122300 0.55 1.45"
  "band1_vc0.9 ss,res_typical,moscap_typical      ss      125 3.63 0.9 1 0 0 6917000 0.55 1.45"
  "band1_vc2.7 ss,res_typical,moscap_typical      ss      125 3.63 2.7 1 0 0 14890400 0.55 1.45"
  "band2_vc0.9 ss,res_typical,moscap_typical      ss      125 3.63 0.9 0 1 0 11464100 0.55 1.45"
  "band6_vc2.7 ss,res_typical,moscap_typical      ss      125 3.63 2.7 0 1 1 232629000 0.55 1.45"
  "band7_vc0.9 ss,res_typical,moscap_typical      ss      125 3.63 0.9 1 1 1 169811000 0.55 1.45"
)

# control_run_one <stage> <libs> <ctag-bundle> <temp> <vdd> <vctrl> <b0> <b1> <b2> <fnom> <win-lo> <win-hi> <run-tag> <mismatch> <seed> <outfile>
control_run_one() {
  local stage="$1" libs="$2" cb="$3" temp="$4" vdd="$5" vctrl="$6"
  local b0="$7" b1="$8" b2="$9" fnom="${10}" wlo="${11}" whi="${12}"
  local runtag="${13}" mism="${14}" seed="${15}" sfile="${16}"
  local ctag="${cb}_${temp}c_${vdd}v"
  local tag="ctl_${stage}_${ctag}_${runtag}"
  stage_netlist "${WORK}/${tag}"
  # Identical window sizing to the sample path this point belongs to -- +/-30%
  # for the single-band scripts' points, 45%/45% for run_band_pair_worst_corner.sh's
  # (#622), carried per point in the CONTROL_POINTS row rather than hardcoded --
  # so the control exercises the same transient the samples it validates were
  # taken from.
  local flo fhi tsettle tstop tmax
  flo=$(awk -v f="${fnom}" -v k="${wlo}" 'BEGIN{print f*k}')
  fhi=$(awk -v f="${fnom}" -v k="${whi}" 'BEGIN{print f*k}')
  tsettle=$(awk -v f="${flo}" 'BEGIN{printf "%.6g", 1.2*4/f}')
  tstop=$(awk -v ts="${tsettle}" -v f="${flo}" 'BEGIN{printf "%.6g", ts + 1.2*7/f}')
  tmax=$(awk -v f="${fhi}" 'BEGIN{printf "%.6g", 1/(80*f)}')
  simenv_run_deck_retried "${DECK}" "${WORK}" "${tag}" "${libs}" "${temp}" \
    "vsup=${vdd}" "vctrl=${vctrl}" "b0v=$((b0))*${vdd}" "b1v=$((b1))*${vdd}" "b2v=$((b2))*${vdd}" \
    "tsettle=${tsettle}" "tstop=${tstop}" "tstep=${tmax}" "tmax=${tmax}" \
    "mc_mismatch=${mism}" "rndseed=${seed}" >/dev/null
  local log="${WORK}/${tag}/ngspice.log" f i
  f=$(simenv_meas "${log}" f1)
  i=$(simenv_meas "${log}" i1)
  [ -n "${f}" ] && [ -n "${i}" ] || { echo "ERROR: missing f1/i1 for ${tag}" >&2; return 1; }
  printf '%s,%s,%s,%s,%s,f1,%s\n' "${stage}" "${ctag}" "${runtag}" "${mism}" "${seed}" "${f}" >>"${sfile}"
  printf '%s,%s,%s,%s,%s,i1,%s\n' "${stage}" "${ctag}" "${runtag}" "${mism}" "${seed}" "${i}" >>"${sfile}"
}

# control_campaign <outfile> -- every point x the five runs, sequential (see
# sim/mc-cp-mismatch/testbench/run.sh's control_campaign for why not xargs).
control_campaign() {
  local sfile="$1" point stage libs cb temp vdd vctrl b0 b1 b2 fnom wlo whi i=0
  : >"${sfile}"
  for point in "${CONTROL_POINTS[@]}"; do
    read -r stage libs cb temp vdd vctrl b0 b1 b2 fnom wlo whi <<<"${point}"
    i=$(( i + 1 ))
    echo "vco-tuning-range control [${i}/${#CONTROL_POINTS[@]}]: ${stage} at ${cb}_${temp}c_${vdd}v, Vctrl=${vctrl} ..."
    control_run_one "${stage}" "${libs}" "${cb}" "${temp}" "${vdd}" "${vctrl}" "${b0}" "${b1}" "${b2}" "${fnom}" "${wlo}" "${whi}" \
      "${SIMENV_CONTROL_RUN_MC1_A1}" 1 "${CONTROL_SEED_A}" "${sfile}"
    control_run_one "${stage}" "${libs}" "${cb}" "${temp}" "${vdd}" "${vctrl}" "${b0}" "${b1}" "${b2}" "${fnom}" "${wlo}" "${whi}" \
      "${SIMENV_CONTROL_RUN_MC1_A2}" 1 "${CONTROL_SEED_A}" "${sfile}"
    control_run_one "${stage}" "${libs}" "${cb}" "${temp}" "${vdd}" "${vctrl}" "${b0}" "${b1}" "${b2}" "${fnom}" "${wlo}" "${whi}" \
      "${SIMENV_CONTROL_RUN_MC1_B}" 1 "${CONTROL_SEED_B}" "${sfile}"
    control_run_one "${stage}" "${libs}" "${cb}" "${temp}" "${vdd}" "${vctrl}" "${b0}" "${b1}" "${b2}" "${fnom}" "${wlo}" "${whi}" \
      "${SIMENV_CONTROL_RUN_MC0_A}" 0 "${CONTROL_SEED_A}" "${sfile}"
    control_run_one "${stage}" "${libs}" "${cb}" "${temp}" "${vdd}" "${vctrl}" "${b0}" "${b1}" "${b2}" "${fnom}" "${wlo}" "${whi}" \
      "${SIMENV_CONTROL_RUN_MC0_B}" 0 "${CONTROL_SEED_B}" "${sfile}"
  done
}

recheck_control() {
  local dir="${1:-}"
  [ -n "${dir}" ] || { echo "usage: run_mismatch.sh --recheck-control <record-id | corners dir>" >&2; exit 2; }
  [ -d "${dir}" ] || dir="${EXP}/corners/${dir}"
  [ -d "${dir}" ] || { echo "ERROR: no such corners directory: ${1}" >&2; exit 1; }
  local csv="${dir}/negative_control.csv"
  [ -f "${csv}" ] || {
    echo "ERROR: ${csv} missing -- that record predates this campaign's own" >&2
    echo "       committed negative control (#602) and delegated the check by" >&2
    echo "       citation to sim/mc-cp-mismatch instead." >&2
    exit 1
  }
  simenv_control_report "${csv}" "vco-tuning-range negative control"
}

case "${1:-}" in
  --one)
    shift
    run_one "$@"
    exit 0
    ;;
  --recheck-control)
    shift
    recheck_control "$@"
    exit 0
    ;;
esac

simenv_require_tools
mkdir -p "${WORK}"

[ -f "${DUT_SRC}" ] || {
  echo "ERROR: ${DUT_SRC} missing -- run design/netlist.sh --top vco" >&2
  exit 1
}

if [ "${1:-}" = "--check" ]; then
  tmpdir=$(mktemp -d)
  trap 'rm -rf "${tmpdir}"' EXIT
  echo "vco-tuning-range mismatch --check: 2 samples per band at ${CORNER_TAG}/${TEMP}C/${VDD}V, Vctrl=${VCTRL}"
  for point in "${BAND_POINTS[@]}"; do
    read -r band b0 b1 b2 fnom <<<"${point}"
    for s in 1 2; do run_one "${band}" "${b0}" "${b1}" "${b2}" "${fnom}" "${s}" "${tmpdir}/out.csv"; done
  done
  echo "${HEADER}"; cat "${tmpdir}/out.csv"
  exit 0
fi

# emit_control_evidence <corners-dir> -- shared by `--control` and the full
# campaign path, so both produce the same bytes from the same code.
emit_control_evidence() {
  local cornersdir="$1"
  local raw="${WORK}/negative_control_rows.csv"
  mkdir -p "${cornersdir}"
  rm -rf "${WORK:?}"/ctl_*
  control_campaign "${raw}"
  local f
  for f in "${WORK}"/ctl_*/ngspice.log; do
    [ -f "${f}" ] || continue
    cp "${f}" "${cornersdir}/$(basename "$(dirname "${f}")").log"
  done
  {
    simenv_provenance "vco-tuning-range (negative control)" "${RID}" \
      "design/netlist/vco.spice (committed export)" \
      "${#CONTROL_POINTS[@]} sampled (corner, Vctrl, band) points x 5 runs (seeds ${CONTROL_SEED_A}/${CONTROL_SEED_B}, sw_stat_mismatch 1 and 0)" \
      "${CONTROL_SWITCHES_NOTE}"
    echo "${SIMENV_CONTROL_HEADER}"
    sort -t, -k1,1 -k2,2 -k3,3 -k6,6 "${raw}"
  } >"${cornersdir}/negative_control.csv"
}

if [ "${1:-}" = "--control" ]; then
  RID=$(simenv_record_id)
  SNAPDIR="${EXP}/netlist-snapshots"
  CORNERSDIR="${EXP}/corners/${RID}"
  RECORDSDIR="${EXP}/records"
  mkdir -p "${SNAPDIR}" "${CORNERSDIR}" "${RECORDSDIR}"
  cp "${DUT_SRC}" "${SNAPDIR}/${RID}-vco-mismatch.spice"
  SHA_VCO=$(simenv_sha256 "${SNAPDIR}/${RID}-vco-mismatch.spice")

  echo "vco-tuning-range --control: ${#CONTROL_POINTS[@]} sampled points x 5 runs"
  emit_control_evidence "${CORNERSDIR}"
  CONTROL_CSV="${CORNERSDIR}/negative_control.csv"
  CONTROL_ROWS="$(simenv_control_md_rows "${CONTROL_CSV}")"
  CONTROL_RC=0
  simenv_control_report "${CONTROL_CSV}" "vco-tuning-range negative control" || CONTROL_RC=$?
  if [ "${CONTROL_RC}" -eq 0 ]; then CONTROL_VERDICT="PASS"; else CONTROL_VERDICT="FAIL"; fi

  RECORD="${RECORDSDIR}/${RID}.md"
  cat >"${RECORD}" <<EOF
# Record ${RID}

- **Record ID**: ${RID}
- **Claim**: a design-input claim, and the one this campaign never made for
  itself -- are \`sim/vco-tuning-range\`'s band-select-mirror Monte Carlo
  draws DETERMINISTIC in \`.option rndseed\`, and GATED BY
  \`sw_stat_mismatch\` rather than by the seed, **in this campaign's own deck,
  DUT and measurement**? This is T1/bronze checklist item 6's "deterministic
  negative control" sub-criterion (#127) for this row, established here
  rather than delegated (#602). Both existing Monte Carlo records in this
  directory -- \`records/20260817-143524-0e9cfc9.md\` and
  \`records/20260923-084925-1655e11.md\` -- discharge that sub-criterion by
  CITING \`sim/mc-cp-mismatch\`'s model-capability finding and saying **"Not
  re-derived here"**. That citation was doubly indirect: it pointed at a
  different DUT (charge pump / PFD, not the VCO bias cascade), a different
  deck and a different measurement, and the sibling's own control was itself
  prose at the time. Those records keep their bytes and their numbers, which
  this record does not touch or re-measure; what changes is that the validity
  leg under them is now committed evidence in this directory, re-derivable by
  \`./run_mismatch.sh --recheck-control ${RID}\` without a simulator.
- **Model-capability gate**: re-derived here, not cited. \`nfet_03v3\`/
  \`pfet_03v3\` (via the \`nfet_03v3_dss\`/\`pfet_03v3_dss\` subcircuits)
  carry independent per-instance \`agauss()\` mismatch draws gated by
  \`sw_stat_mismatch\`, parsed once at netlist PARSE time and reproducible
  via \`.option rndseed=N\`. Every point in the Result table below
  re-establishes that on this campaign's own DUT.
- **Netlist provenance**: committed export \`design/netlist/vco.spice\` (the
  same DUT \`tb_vco_tuning.spice\` composes and both Monte Carlo records
  sample, unmodified), frozen into
  \`sim/vco-tuning-range/netlist-snapshots/${RID}-vco-mismatch.spice\`,
  SHA-256 \`${SHA_VCO}\`. Testbench deck: this campaign's own
  \`tb_vco_mismatch.sp\`, with ONE change made for this record (#602) --
  \`sw_stat_mismatch\` is now \`'mc_mismatch'\` instead of a pinned literal
  \`1\`, because a deck that cannot be run with the switch OFF cannot have a
  negative control. \`mc_mismatch\` has no default in the deck, so an
  invocation that forgets it fails at parse time instead of silently
  producing a mismatch-free "Monte Carlo" sample. Verified by direct
  experiment: \`mc_mismatch=1\` reproduces the pinned-literal deck's output
  exactly, so the production sample path is unchanged.
- **Environment provenance**:
$(simenv_env_block "N/A -- design/netlist/vco.spice is a committed export, this testbench includes it directly (same convention as tb_vco_tuning.sp/.spice's pre-harness sibling)" \
  "\`design.ngspice\` included first via sim/lib/simenv.sh's simenv_run_deck; this record runs each point at BOTH \`sw_stat_mismatch = 1\` and \`sw_stat_mismatch = 0\` (via the deck's \`mc_mismatch\` handle, see Netlist provenance) -- comparing the two IS the measurement. \`sw_stat_global\` stays 0 throughout, with \`.option rndseed\` set per run")
- **Corner matrix run**: **${#CONTROL_POINTS[@]} (corner, temperature, supply,
  Vctrl, band) points** -- every point the Monte Carlo sample records in this
  experiment directory actually sample, and no others. The exact list, with each
  point's band-select code, nominal-frequency window sizing and transient-window
  bracket, is \`CONTROL_POINTS\` in \`testbench/run_mismatch.sh\`; the committed
  \`corners/${RID}/negative_control.csv\` names each point in its own rows. In
  groups:
  - \`typical\`/27C/3.30V (-> \`.lib\` sections \`typical\`, \`res_typical\`,
    \`moscap_typical\`), Vctrl = 1.8 V, bands 0 and 7
    (\`records/20260817-143524-0e9cfc9.md\`'s points), and \`ss\`/125C/3.63V
    (-> \`ss\`, \`res_typical\`, \`moscap_typical\`), Vctrl = 2.7 V, band 0
    (\`records/20260923-084925-1655e11.md\`'s point).
  - **All five MOS bundles** (\`typical\`, \`ff\`, \`fs\`, \`sf\`, \`ss\`) at
    125C/3.63V, bands 3 and 4 at Vctrl = 2.7 V and 0.9 V respectively -- the two
    ends of the B3 -> B4 pair, which is the deterministically thinnest adjacent
    pair at every bundle.
  - \`ss\` at the other three vertices of the temperature x supply box
    (-40C/2.97V, -40C/3.63V, 125C/2.97V), same two bands and Vctrl values.
  - \`ss\`/125C/3.63V at both ends of the B0 -> B1, B1 -> B2 and B6 -> B7 pairs
    (bands 0,1,2,6,7 across Vctrl = 2.7 V and 0.9 V as each pair requires).

  The last three groups are \`run_band_pair_worst_corner.sh\`'s 11-point
  joint-draw grid, decomposed into its single-band ends (#622).
  **Axes not swept**: the 27C temperature and 3.30V supply mid-points except
  where the first group already visits them; the composite \`all-slow\`/
  \`all-fast\` bundles; band 5; and the five intermediate Vctrl points.
  **Justification** (sim/README.md's "Default corner matrix" rule requires
  one for any subset): a control's grid is the grid of the samples it
  validates -- signoff/README.md's "Item 6(c)" states that reading, and it is
  the whole rule governing this field. Every point above is a point some
  committed sample record in this directory draws at, and every point those
  records draw at is above. The sample grid's own justification for being the
  subset it is belongs to the sample records, not here.
- **Methodology / criteria / limitations**:
  - **Five runs per point**, three legs derived from them -- \`repeat\`
    (mismatch ON, seed ${CONTROL_SEED_A}, twice) must be identical; \`vary\`
    (mismatch ON, seed ${CONTROL_SEED_A} vs ${CONTROL_SEED_B}) must DIFFER;
    \`gate\` (mismatch OFF, seed ${CONTROL_SEED_A} vs ${CONTROL_SEED_B}) must
    be identical. Schema and rationale: \`sim/lib/simenv.sh\`'s "Monte Carlo
    negative control" section.
  - **Same window sizing and same readout as the production samples** --
    \`f = 4 / tp\` off the buffered \`CLK\` output after \`tsettle\`, plus the
    supply current \`i1\`, with the transient window sized off each point's own
    systematic nominal frequency and its own sample path's bracket: +/-30% for
    the points \`run_one\`/\`run_band0_worst_corner.sh\` sample, 45%/45% for the
    points \`run_band_pair_worst_corner.sh\` samples (that script needs the wider
    window to hold a mismatched frequency past 3 sigma, and a control run through
    a narrower transient than its samples is not a control for them). The bracket
    travels with each \`CONTROL_POINTS\` row for exactly that reason.
  - **Values compared as TEXT, not within a tolerance** -- a tolerance would
    let a drifting draw keep passing.
  - **ONE DECK, deliberately: the single-band \`tb_vco_mismatch.sp\`, including
    for the points whose samples come from the two-band
    \`tb_vco_band_pair.sp\`.** What the three legs establish is a property of the
    MODEL AND THE PARSE at a given corner -- that the \`agauss()\` draws are
    deterministic in \`.option rndseed\` and gated by \`sw_stat_mismatch\` -- and
    that property is per (corner, temperature, supply, band, Vctrl), which is
    what this grid enumerates. It is NOT a check that the two-band deck's two
    \`tran\` analyses see the same draw; that is a separate claim, and it is
    established where it belongs, in \`tb_vco_band_pair.sp\`'s own sample
    records, whose committed per-draw logs hold both analyses under one parse for
    a reader to see. Stated here so the deck axis is read as a named residual
    rather than as coverage this record implies and does not have.
  - **What this record does NOT establish**: the adequacy of this campaign's
    sample count (item 6's sub-criterion (b) is a separate reading), the
    justification for the sample grid being the subset it is -- that belongs to
    the sample records' own "Corner matrix run" fields -- and no
    frequency-dispersion figure: it re-measures none of the sample records'
    numbers and supersedes none of them.
  - **Read the CSV's \`sw_stat_mismatch\` COLUMN, not its \`# switches:\`
    header line.** This artifact deliberately runs BOTH switch values, so no
    single header sentence can state its switches (#601's fifth
    \`simenv_provenance\` argument says as much, in prose, for exactly this
    reason); column 4 of each data row is authoritative. A record minted
    before this note was wired (see the erratum in this file's header
    comment) shipped the unconditional design.ngspice-default header instead.
- **Statistical convention**: N/A as a distribution claim -- no mean, sigma
  or \`|mean|+3sigma\` is reported and no distribution is sampled. The switch
  settings are the measurement: \`sw_stat_global = 0\` throughout,
  \`sw_stat_mismatch\` taking both 1 and 0, seeds ${CONTROL_SEED_A} and
  ${CONTROL_SEED_B} via \`.option rndseed\`. Every run's raw log is committed
  under \`corners/${RID}/\`.
- **Result -- ${CONTROL_VERDICT}**, per (band + Vctrl, corner) point, all
  ${#CONTROL_POINTS[@]} of them:

  | Band @ Vctrl | Corner | \`repeat\` same seed -> identical | \`vary\` other seed -> differs | \`gate\` mismatch=0 -> seed-independent | Metrics that varied |
  |---|---|---|---|---|---|
${CONTROL_ROWS}

  Derived from \`corners/${RID}/negative_control.csv\`, not written by hand.
  \`./run_mismatch.sh --recheck-control ${RID}\` reproduces it from the
  committed bytes with no simulator and exits non-zero if any leg fails.
- **Links**:
  - Testbench: \`sim/vco-tuning-range/testbench/tb_vco_mismatch.sp\`,
    \`run_mismatch.sh\` (\`--control\` / \`--recheck-control\`),
    \`run_band0_worst_corner.sh\` (the third point's sample script),
    \`run_band_pair_worst_corner.sh\` (the joint-draw grid whose points groups
    2-4 above cover; \`--grid\` prints that grid with no simulator)
  - Design: \`design/vco.sch\`, \`design/vco_bias.sch\`
  - Netlist snapshot:
    \`sim/vco-tuning-range/netlist-snapshots/${RID}-vco-mismatch.spice\`
  - Raw logs: \`sim/vco-tuning-range/corners/${RID}/\`
  - Extracted metrics:
    \`sim/vco-tuning-range/corners/${RID}/negative_control.csv\`
  - Sample records this control validates (none superseded):
    \`sim/vco-tuning-range/records/20260817-143524-0e9cfc9.md\`,
    \`sim/vco-tuning-range/records/20260923-084925-1655e11.md\`,
    \`sim/vco-tuning-range/records/20260927-081930-d004d5b.md\`,
    and the ${#CONTROL_POINTS[@]}-point grid's own sample record minted by
    \`run_band_pair_worst_corner.sh\` (#622)
  - Sibling campaign's own control (same three legs, same schema):
    \`sim/mc-cp-mismatch/records/\`
- **Timestamp / author**: $(date -u +%Y-%m-%dT%H:%M:%SZ), agent-builder (issues #602, #622)
$(simenv_supersedes_field "${SIM_SUPERSEDES:-}")
EOF
  echo "vco-tuning-range: wrote ${RECORD}"
  echo "vco-tuning-range: wrote ${CONTROL_CSV}"
  exit "${CONTROL_RC}"
fi

echo "vco-tuning-range mismatch: N_SAMPLES=${N_SAMPLES}/band x ${#BAND_POINTS[@]} bands at ${CORNER_TAG}/${TEMP}C/${VDD}V, Vctrl=${VCTRL}, $(simenv_jobs) parallel jobs"

rm -f "${WORK}"/band*.csv

for point in "${BAND_POINTS[@]}"; do
  read -r band b0 b1 b2 fnom <<<"${point}"
  echo "vco-tuning-range mismatch: band${band} ..."
  seq 1 "${N_SAMPLES}" | xargs -P "$(simenv_jobs)" -I{} \
    "${BASH:-/bin/bash}" -c "\"${HERE}/run_mismatch.sh\" --one ${band} ${b0} ${b1} ${b2} ${fnom} {} \"${WORK}/band${band}_{}.csv\""
done

cat "${WORK}"/band*.csv | sort -t, -k1,1n -k2,2n >"${WORK}/all.csv"

GOT=$(wc -l <"${WORK}/all.csv" | tr -d ' ')
EXPECT=$(( N_SAMPLES * ${#BAND_POINTS[@]} ))
[ "${GOT}" -eq "${EXPECT}" ] || { echo "ERROR: expected ${EXPECT} rows, got ${GOT}" >&2; exit 1; }

# --------------------------------------------------------------------------
# Mint the evidence record.
# --------------------------------------------------------------------------
RID=$(simenv_record_id)
SNAPDIR="${EXP}/netlist-snapshots"
CORNERSDIR="${EXP}/corners/${RID}"
RECORDSDIR="${EXP}/records"
mkdir -p "${SNAPDIR}" "${CORNERSDIR}" "${RECORDSDIR}"

cp "${DUT_SRC}" "${SNAPDIR}/${RID}-vco-mismatch.spice"
SHA_VCO=$(simenv_sha256 "${SNAPDIR}/${RID}-vco-mismatch.spice")

for f in "${WORK}"/band*_seed*/ngspice.log; do
  [ -f "${f}" ] || continue
  cp "${f}" "${CORNERSDIR}/$(basename "$(dirname "${f}")")_${CORNER_TAG}_${TEMP}c_${VDD}v.log"
done

OUT="${CORNERSDIR}/mismatch.csv"
{
  simenv_provenance "vco-tuning-range (band-select mirror mismatch)" "${RID}" \
    "design/netlist/vco.spice (committed export)" \
    "${CORNER_TAG}/${TEMP}C/${VDD}V, Vctrl=${VCTRL}, bands={0,7}, N=${N_SAMPLES} mismatch samples/band" \
    "${SWITCHES_NOTE}"
  echo "${HEADER}"; cat "${WORK}/all.csv"
} >"${OUT}"

# --------------------------------------------------------------------------
# Negative control, run and committed alongside the samples it validates
# (#602). Before this, this campaign had none of its own and its records
# delegated the check by citation to sim/mc-cp-mismatch.
# --------------------------------------------------------------------------
echo "vco-tuning-range mismatch: negative control (${#CONTROL_POINTS[@]} points x 5 runs) ..."
emit_control_evidence "${CORNERSDIR}"
CONTROL_CSV="${CORNERSDIR}/negative_control.csv"
CONTROL_ROWS="$(simenv_control_md_rows "${CONTROL_CSV}")"
CONTROL_RC=0
simenv_control_report "${CONTROL_CSV}" "vco-tuning-range negative control" || CONTROL_RC=$?
if [ "${CONTROL_RC}" -eq 0 ]; then CONTROL_VERDICT="PASS"; else CONTROL_VERDICT="FAIL"; fi

stats_band() {
  local band="$1" field="$2"
  simenv_datarows "${OUT}" | awk -F, -v b="${band}" -v f="${field}" '$1==b {print $f}' | simenv_stats_from_values
}

B0_F=$(stats_band 0 3); B0_F_M=$(echo "${B0_F}" | awk '{print $1}'); B0_F_SD=$(echo "${B0_F}" | awk '{print $2}'); B0_F_N=$(echo "${B0_F}" | awk '{print $3}')
B7_F=$(stats_band 7 3); B7_F_M=$(echo "${B7_F}" | awk '{print $1}'); B7_F_SD=$(echo "${B7_F}" | awk '{print $2}'); B7_F_N=$(echo "${B7_F}" | awk '{print $3}')

pct3s() { awk -v m="$1" -v s="$2" 'BEGIN{printf "%.4g", 300*s/m}'; }
B0_F_3SPCT=$(pct3s "${B0_F_M}" "${B0_F_SD}")
B7_F_3SPCT=$(pct3s "${B7_F_M}" "${B7_F_SD}")

echo "band0 f: mean=${B0_F_M} Hz sd=${B0_F_SD} Hz (+-3sigma = ${B0_F_3SPCT}% of mean, n=${B0_F_N})"
echo "band7 f: mean=${B7_F_M} Hz sd=${B7_F_SD} Hz (+-3sigma = ${B7_F_3SPCT}% of mean, n=${B7_F_N})"

# --------------------------------------------------------------------------
# Headroom comparison, computed (not hardcoded prose) so the record's own
# words cannot silently drift from the numbers above. `HEADROOM_PCT` is the
# fractional overlap `sim/vco-tuning-range/records/20260804-164956-72883fb.md`'s
# band_overlap check found at its worst pair/corner (overlap ratio 1.268 =>
# 26.8%) -- see this record's Result field for the full caveat on why this
# is an order-of-magnitude sanity flag, not a formal combined check (a
# one-sided log-frequency overlap margin vs. a two-sided +/-3sigma
# dispersion-of-the-mean figure are not the same quantity). A band whose
# dispersion exceeds that headroom is flagged OVER, not silently rounded
# into a reassuring "well under" -- band 0's measured 38.79%-class result is
# exactly the case this guard exists for: the previous, unconditional prose
# ("both bands are well under") was FALSE for band 0 the first time this
# script produced real numbers, caught by a builder review before the
# record was committed (#146). Never repeat that mistake by hand-writing
# the verdict again.
HEADROOM_PCT=26.8
headroom_verdict() { awk -v p="$1" -v h="${HEADROOM_PCT}" 'BEGIN{print (p<=h)?"under":"OVER"}'; }
B0_HEADROOM_VERDICT=$(headroom_verdict "${B0_F_3SPCT}")
B7_HEADROOM_VERDICT=$(headroom_verdict "${B7_F_3SPCT}")
echo "band0 vs ${HEADROOM_PCT}% headroom: ${B0_HEADROOM_VERDICT}"
echo "band7 vs ${HEADROOM_PCT}% headroom: ${B7_HEADROOM_VERDICT}"

RECORD="${RECORDSDIR}/${RID}.md"
cat >"${RECORD}" <<EOF
# Record ${RID}

- **Record ID**: ${RID}
- **Claim**: #8 / design/README.md's "3-bit band-select mirror" -- does
  RANDOM device (Vth/beta) mismatch in the band-select mirror cascade
  (\`design/vco_bias.sch\`'s three cascaded current mirrors, see
  design/README.md's "Band map: a geometric mirror cascade" section) shift
  the VCO's oscillation frequency enough to matter against the systematic
  f(Vctrl)/band-plan curve \`testbench/tb.json\`'s harness-driven sweep
  measures (\`sw_stat_mismatch = 0\` there -- an explicitly documented gap in
  every prior \`sim/vco-tuning-range/\` record's methodology field, closed by
  this record). This is the second half of #146 (the first half extends
  \`sim/mc-cp-mismatch/\` with a corner-combined Monte Carlo record).
  Spec-line references are placeholders pending ratification (#1):
  \`spec/pll.md#output-band\`, \`spec/pll.md#kvco\`.
- **Model-capability gate**: \`nfet_03v3\`/\`pfet_03v3\` (via the
  \`nfet_03v3_dss\`/\`pfet_03v3_dss\` subcircuits) carry independent
  per-instance \`agauss()\` mismatch draws gated by \`sw_stat_mismatch\`,
  parsed once at netlist PARSE time, reproducible via \`.option rndseed=N\`.
  That reproducibility claim is HOST-SCOPED -- same host, same build, same
  seed -> same draw; a different host is an independent replicate, not a
  reproduction of the same sample -- see sim/README.md's "Statistical
  convention" field. The finding originates in
  \`sim/mc-cp-mismatch/records/20260731-212614-640560e.md\`, but this record
  no longer takes it on citation the way earlier records of this campaign did
  ("Not re-derived here"): it is **re-derived on this campaign's own DUT,
  deck and measurement** by the negative control below, whose verdict is in
  this record's Result field and whose bytes are in
  \`corners/${RID}/negative_control.csv\` (#602).
- **Why a raw \`sim/lib/simenv.sh\` deck, not a \`testbench/tb.json\` manifest
  edit**: see \`run_mismatch.sh\`'s header comment for the full finding --
  in short, \`sim/harness/runner.py\`'s \`compose_deck()\` emits a manifest's
  \`params\` BEFORE \`.include design.ngspice\`, so a tb.json
  \`sw_stat_mismatch\` override is silently nullified by design.ngspice's own
  later-in-deck default (confirmed by direct ngspice-46 experiment: last
  \`.param\` redefinition in deck order wins). The harness also has no Monte
  Carlo seed axis. \`testbench/tb.json\`'s own 45-corner harness sweep is
  UNCHANGED and UNTOUCHED by this record (still \`sw_stat_mismatch = 0\`,
  still the systematic claim) -- this record is additive, reusing
  \`sim/mc-cp-mismatch\`'s pre-harness pattern for the one thing the harness
  cannot yet do.
- **Netlist provenance**: committed export \`design/netlist/vco.spice\`
  (same DUT \`testbench/tb_vco_tuning.spice\` composes, unmodified by this
  record), frozen into
  \`sim/vco-tuning-range/netlist-snapshots/${RID}-vco-mismatch.spice\`,
  SHA-256 \`${SHA_VCO}\`. Testbench deck (\`tb_vco_mismatch.sp\`) contains
  stimulus, measurement and the \`sw_stat_mismatch\`/\`rndseed\` overrides
  only -- one VCO instance instead of \`tb_vco_tuning.sp/.spice\`'s seven, no
  other change to the DUT.
- **Environment provenance**:
$(simenv_env_block "N/A -- design/netlist/vco.spice is a committed export, this testbench includes it directly (same convention as tb_vco_tuning.sp/.spice's pre-harness sibling)" \
  "\`design.ngspice\` included first via sim/lib/simenv.sh's simenv_run_deck; this campaign's own deck (tb_vco_mismatch.sp) then declares sw_stat_global=0 / sw_stat_mismatch=1, positioned after the design.ngspice include specifically so the later declaration wins -- see this record's own note on the harness-ordering finding above; sw_stat_mismatch defaults to 0 in every OTHER sim/vco-tuning-range/ record, including this campaign's own harness-driven testbench/tb.json sweep, unaffected by this file")
- **Corner matrix run**: ONE nominal PVT point -- \`${CORNER_TAG}\` (-> \`.lib\`
  section \`typical\`) / ${TEMP} C / ${VDD} V, Vctrl = ${VCTRL} V (mid-window).
  **Axes not swept**: temperature, supply, MOS process corner, Vctrl (beyond
  the one mid-window point) and 6 of the 8 band codes are all fixed/omitted.
  **Justification** (sim/README.md's "Default corner matrix" rule): same
  reasoning as \`sim/mc-cp-mismatch\`'s original nominal-only record -- corner
  sensitivity of the MEAN f(Vctrl) curve is already \`testbench/tb.json\`'s
  45-corner harness sweep's job; this record's job is the DISPERSION random
  mismatch adds on top, and Pelgrom-mismatch dispersion is not expected to
  carry strong PVT dependence the way a systematic mechanism would. Band 0
  and band 7 are chosen as the two ends of the band-select mirror's cascade
  activation (band 0: only the three always-on legs; band 7: every switched
  leg active, the full three-mirror cascade) -- the intermediate 6 band codes
  and the rest of the Vctrl window are not sampled, a genuine limitation a
  future pass could widen.
- **Methodology / criteria / limitations**:
  - Single VCO copy (not \`tb_vco_tuning.sp/.spice\`'s seven), at Vctrl =
    ${VCTRL} V, band 0 or band 7, \`N_SAMPLES=${N_SAMPLES}\` single-instance
    invocations per band (\`$(( N_SAMPLES * 2 ))\` total), one \`.option
    rndseed\` per sample. Measurement criterion identical to
    \`tb_vco_tuning.sp/.spice\`: \`f = 4 / tp\`, \`tp\` from the first to the
    fifth rising half-supply crossing of the buffered \`CLK\` output after
    \`tsettle\` (>= 4 estimated periods), so the bias generator's own
    start-up transient is excluded.
  - **Transient window**: sized off the SYSTEMATIC nominal frequency at each
    band (from
    \`sim/vco-tuning-range/records/20260804-164956-72883fb.md\`'s
    \`raw_measures.csv\`, \`typical/27C/3.30V\`, \`Vctrl=1.8V\`: band0
    ${BAND_POINTS[0]##* } Hz, band7 ${BAND_POINTS[1]##* } Hz) with a +/-30%
    margin either side -- never trusted for a result, only for
    \`tstep\`/\`tstop\` sizing; a missed \`.meas\` trigger would fail the
    sample rather than silently mis-measure it.
  - **No numeric budget exists for this term.** Unlike
    \`sim/mc-cp-mismatch\`'s charge-pump terms, design/README.md carries no
    "band-select mirror mismatch budget" table -- this record reports the
    measured dispersion as a characterization, not a pass/fail verdict, the
    same honest handling \`mc-cp-mismatch\` already uses for its
    divider-retiming-flop term (also not itself a budget-table line).
  - **Two band codes only, one Vctrl point.** A future, more complete pass
    would sweep the intermediate 6 band codes and more of the Vctrl window;
    this record characterizes the cascade's two activation extremes as an
    initial, honestly-scoped pass, matching this repo's evidence culture of
    a stated, narrower claim over a fabricated broad one.
  - Bias generation is NOT idealized here (unlike \`sim/mc-cp-mismatch\`'s
    charge-pump decks) -- the full \`vco_bias\` subcircuit, including its own
    mirror devices, is part of the DUT, so this record's dispersion already
    includes the bias generator's own mismatch contribution alongside the
    band-select mirror's.
- **Statistical convention**: \`sw_stat_global = 0\`, \`sw_stat_mismatch = 1\`
  (mismatch-only, global process variation off, matching every other Monte
  Carlo campaign in this repo). \`N_SAMPLES=${N_SAMPLES}\` per band. Seeds:
  sequential integers \`1..N\` per band, passed via \`.option rndseed\`; every
  seed's raw log is committed under \`corners/${RID}/\`.
- **Negative control (#602)**: this campaign's own, run as part of this
  campaign and committed beside its samples -- not a citation to
  \`sim/mc-cp-mismatch\`, which is how every earlier record of this campaign
  discharged item 6's control sub-criterion. Three legs per point:
  \`repeat\` (mismatch ON, seed ${CONTROL_SEED_A}, twice) identical;
  \`vary\` (mismatch ON, seeds ${CONTROL_SEED_A} vs ${CONTROL_SEED_B})
  DIFFERENT; \`gate\` (mismatch OFF, same two seeds) identical. The \`vary\`
  leg is what stops the other two from being equally satisfied by a
  measurement insensitive to everything. Overall: **${CONTROL_VERDICT}** --
  see the control table in the Result field, and re-derive it from committed
  bytes with \`./run_mismatch.sh --recheck-control ${RID}\` (no simulator).
- **Result -- negative control -- ${CONTROL_VERDICT}**:

  | Band | Corner | \`repeat\` same seed -> identical | \`vary\` other seed -> differs | \`gate\` mismatch=0 -> seed-independent | Metrics that varied |
  |---|---|---|---|---|---|
${CONTROL_ROWS}

  Derived from \`corners/${RID}/negative_control.csv\`, not written by hand.
- **Result**:

  | Band | f mean | f sd | \|mean\|+3sigma as %% of mean | vs. ${HEADROOM_PCT}% headroom (see below) | n |
  |---|---|---|---|---|---|
  | 0 (no switched leg) | ${B0_F_M} Hz | ${B0_F_SD} Hz | ${B0_F_3SPCT}% | **${B0_HEADROOM_VERDICT}** | ${B0_F_N} |
  | 7 (full cascade) | ${B7_F_M} Hz | ${B7_F_SD} Hz | ${B7_F_3SPCT}% | **${B7_HEADROOM_VERDICT}** | ${B7_F_N} |

  Compare against \`sim/vco-tuning-range/records/20260804-164956-72883fb.md\`'s
  worst adjacent-overlap ratio (1.268, \`ss/125C/3.63V\`) -- the margin that
  ratio carries above 1.0 is the headroom this dispersion draws against
  before mismatch alone could open a coverage hole at a band edge, expressed
  here as ${HEADROOM_PCT}% (the fractional part of the 1.268 ratio). **This
  is not a symmetric statement across both bands, and the two verdicts above
  are reported exactly as measured, not smoothed into one blanket
  conclusion.** Band 7 (full cascade, highest bias current) is comfortably
  UNDER headroom -- Pelgrom mismatch scales down with device current, so the
  highest-current band shows the tightest relative dispersion, as expected.
  Band 0 (only the always-on legs, the LOWEST bias current in the band plan)
  measures \`|mean|+3sigma\` OVER the 26.8% headroom figure: at this band's
  low bias current, per-instance Vth/beta mismatch is a much larger fraction
  of the drive, so its relative frequency dispersion is large enough that, in
  the worst case, random mismatch alone could plausibly erode band 0's
  adjacent-overlap margin against band 1 -- a genuine, not-yet-formally-closed
  finding, reported honestly rather than rounded down to a reassuring
  headline. **What this is NOT**: a formal combined verdict. The two source
  records' PVT points differ (this record is nominal-only \`typical/27C/3.30V\`;
  the 1.268 ratio is \`ss/125C/3.63V\`, a different corner entirely), band 0's
  own overlap ratio at its worst corner is not reproduced here, and
  \`n=${N_SAMPLES}/band\` is far short of the statistical power a real
  budget-table verdict would need. A follow-on record combining this
  campaign's per-band Monte Carlo with the systematic sweep's own worst-corner
  band-0-specific overlap ratio (not the worst-pair-overall figure used here
  as an order-of-magnitude proxy) would be needed to turn "band 0's dispersion
  looks large enough to matter" into an actual pass/fail coverage-hole check.
- **Links**:
  - Testbench: \`sim/vco-tuning-range/testbench/tb_vco_mismatch.sp\`,
    \`run_mismatch.sh\`
  - Design: \`design/vco.sch\`, \`design/vco_bias.sch\`, \`design/vco_stage.sch\`
  - Netlist snapshot:
    \`sim/vco-tuning-range/netlist-snapshots/${RID}-vco-mismatch.spice\`
  - Raw logs: \`sim/vco-tuning-range/corners/${RID}/\`
  - Extracted metrics: \`sim/vco-tuning-range/corners/${RID}/mismatch.csv\`
  - Systematic sweep this record adds dispersion on top of (unchanged,
    untouched): \`sim/vco-tuning-range/testbench/tb.json\`,
    \`sim/vco-tuning-range/records/20260804-164956-72883fb.md\`
  - Sibling Monte Carlo methodology (parse-time-seed finding, corner-combined
    precedent): \`sim/mc-cp-mismatch/\`
- **Timestamp / author**: $(date -u +%Y-%m-%dT%H:%M:%SZ), agent-builder (issue #146)
$(simenv_supersedes_field "${SIM_SUPERSEDES:-}")
EOF

echo "vco-tuning-range mismatch: wrote ${RECORD}"
echo "vco-tuning-range mismatch: wrote ${OUT}"
echo "vco-tuning-range mismatch: wrote ${CORNERSDIR}/ ($(( N_SAMPLES * 2 )) corner logs)"
