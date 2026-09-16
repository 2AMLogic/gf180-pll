#!/usr/bin/env bash
# gf180-pll :: supply-sensitivity :: the post-supply-step re-lock campaign
# (#395, DR-011 Decision 4)
#
#   ./relock_campaign.sh [record-id]
#
# One command, so the campaign behind the record is reproducible rather than a
# sequence of environment variables someone has to reconstruct from prose.  It
#   1. runs the step/ramp deck at the SCOPED corner set below, with the
#      high-plateau hold pushed out past `lock` re-assertion;
#   2. archives each run's generated deck + ngspice output, its decimated
#      transient and its per-REF-cycle phase trace into corners/<record-id>/,
#      and freezes the DUT netlist snapshot;
#   3. runs relock_measurement.sh over that directory.
#
# ---------------------------------------------------------------------------
# SCOPE, decided before the run and not after it (#395 asks for this first)
# ---------------------------------------------------------------------------
# CORNERS: the same three `20260901-155456-46b92f8` ran the step/ramp deck at
# -- `typical`/27 C, `ss`/-40 C, `ff`/125 C -- at the same band code and the
# same warm-start control voltage, read from that run's own committed logs.
#
# Why not more: the question #395 exists to settle is falsifiable and specific.
# `20260915-202323-62391c6` brackets the post-step re-lock at 37.2 .. 42.6 us
# after the step edge AT THOSE CORNERS, and DR-011 Decision 1 ("no change to
# the loop filter") rests on that bracket.  Testing it means re-running THOSE
# corners for longer.  A fourth corner would not test it; it would start the
# different campaign -- does a post-excursion settling bound generalise across
# the 45-point grid -- that DR-011's own Consequences section flags and that is
# filed separately.  Widening scope here would have traded the one question
# that can be answered for a sample too thin to answer either.
#
# EXCURSION: one, and it is the same one -- 3.30 -> 3.63 V (+10 % of nominal)
# with a 100 ns edge, f_ref = 12.5 MHz, N = 8, Icp trim code 2.  Identical to
# the run this extends, deliberately: the result has to be directly comparable
# to that run's 34.40 us lower bound, and a different excursion size measures a
# different quantity rather than measuring this one for longer.
#
# HOLD: the only thing that changes.  t_ramp moves from 41.1 us to 76.8 us, so
# the post-step hold runs 71.1 us (7.64 tau) past the end of the step edge
# instead of 34.4 us (3.70 tau).  That number is chosen, not rounded to: 71 us
# is this loop's own worst small-signal 1 % settling time under the trim rule
# (spec/pll.md "Lock time", DR-006), so a hold that reaches it has given the
# loop the longest settling spec/pll.md itself documents for it.  It is also
# 1.67x the top of the bracket being tested (42.6 us), so a re-lock inside the
# bracket is measured with margin and a re-lock outside it is still bounded
# from below by a number 2.07x stronger than the one DR-011 had to state.
# t_rend and tstop follow it, preserving the ramp's own 103 mV/us rate and the
# 8.0 us post-ramp hold, so the ramp and END-plateau measurements stay valid
# and comparable rather than being truncated.
#
# p7/p8 are pinned to the escalated run's OWN instants (36.9u/40.1u).  The
# profile is then identical to that run's everywhere before its t_ramp, so
# `phi07`/`phi08`/`ferr_hi` must reproduce its committed values -- a
# reproducibility check this campaign gets for free and reports in its record.
#
# COST, stated up front as DR-011 did: the 40.08 us-hold runs this extends took
# 8893 .. 9070 s of analysis time each.  This profile is 1.64x longer, so
# budget ~4 h per corner; the three run concurrently.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP="$(cd "${HERE}/.." && pwd)"
ROOT="$(cd "${EXP}/../.." && pwd)"
# shellcheck source=../../lib/simenv.sh
. "${ROOT}/sim/lib/simenv.sh"

WORK="${EXP}/work"
RID="${1:-$(simenv_record_id)}"
OUT="${EXP}/corners/${RID}"
SNAPDIR="${EXP}/netlist-snapshots"
PRIOR="${EXP}/corners/20260901-155456-46b92f8"

# The scoped corner set: bundle temp band vctrl0.  band and vctrl0 are READ
# FROM the prior run's committed logs rather than re-derived, so this campaign
# starts the loop from the identical warm state that one did.
CORNERS=(
  "typical 27  5 2.1618"
  "ss      -40 5 2.2266"
  "ff      125 5 2.0230"
)

# The hold, and everything the hold carries with it.  See the SCOPE block above
# for why each value is what it is.
export SIM_DYN_TRAMP=76.8u
export SIM_DYN_TREND=83.2u
export SIM_DYN_TSTOP=91.2u
export SIM_DYN_TA_HI=36.9u
export SIM_DYN_TB_HI=40.1u

simenv_require_tools
mkdir -p "${WORK}" "${OUT}" "${SNAPDIR}"

echo "relock_campaign: record ${RID}; ${#CORNERS[@]} corners, hold to ${SIM_DYN_TRAMP} (t_ramp), tstop ${SIM_DYN_TSTOP}"

# --- 1. run ----------------------------------------------------------------
# Concurrently: each is a single-threaded ngspice process and they are
# independent.  --one-dyn is resumable on an exact match of the deck mtime AND
# the full parameter list, so re-running this script after a completed campaign
# re-archives and re-analyses without re-simulating.
pids=()
for row in "${CORNERS[@]}"; do
  # shellcheck disable=SC2086  # intentional word-splitting of the corner row
  set -- ${row}; b="$1"; t="$2"; band="$3"; vc0="$4"
  "${HERE}/run.sh" --one-dyn "${b}" "${t}" "${band}" "${vc0}" \
    "${WORK}/sdynrl_${b}_${t}.csv" "${WORK}/waverl_${b}_${t}.csv" &
  pids+=("$!")
done
rc=0
for p in "${pids[@]}"; do wait "${p}" || rc=1; done
[ "${rc}" -eq 0 ] || { echo "ERROR: at least one step/ramp run failed" >&2; exit 1; }

# --- 2. archive ------------------------------------------------------------
cp "${WORK}/dut_dyn.sp" "${SNAPDIR}/${RID}-dyn.spice"
for row in "${CORNERS[@]}"; do
  # shellcheck disable=SC2086
  set -- ${row}; b="$1"; t="$2"
  tag="dyn_${b}_T${t}_X${SIM_DYN_TRAMP}"; tag="$(simenv_mktag "${tag}")"
  cid="$(simenv_corner_id "${b}" "${t}" 3.30)"
  simenv_archive_log "${WORK}" "${tag}" "${OUT}" "dynrl_${cid}"
  cp "${WORK}/waverl_${b}_${t}.csv"       "${OUT}/supply_transient_${cid}_relock.csv"
  cp "${WORK}/waverl_${b}_${t}_phase.csv" "${OUT}/supply_phase_${cid}_relock.csv"
  cp "${WORK}/sdynrl_${b}_${t}.csv"       "${OUT}/sdyn_row_${cid}_relock.csv"
done

# The prior run's steady-state grid is READ by the analysis (the structural
# gate) and is not copied: it belongs to its own record and stays there.
[ -f "${PRIOR}/supply_steady.csv" ] || {
  echo "ERROR: ${PRIOR}/supply_steady.csv missing -- the structural gate has no source" >&2; exit 1; }

# --- 3. analyse ------------------------------------------------------------
"${HERE}/relock_measurement.sh" "${RID}" "${OUT}"

echo
echo "relock_campaign: netlist snapshot ${SNAPDIR}/${RID}-dyn.spice"
echo "relock_campaign: sha256 $(simenv_sha256 "${SNAPDIR}/${RID}-dyn.spice")"
