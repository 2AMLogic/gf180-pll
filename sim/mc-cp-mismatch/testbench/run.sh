#!/usr/bin/env bash
# gf180-pll :: mc-cp-mismatch :: Monte Carlo runner for the charge-pump
# mismatch budget (#15), checked against design/README.md's "Up/down
# mismatch budget" table.
#
# Four sub-campaigns, one record (they substantiate one claim -- "how far
# does RANDOM device mismatch actually push the charge-pump/PFD static phase
# error and reference-spur budget, on top of the SYSTEMATIC values
# cp-compliance and pfd-deadzone already measure, and does that dispersion
# still hold once temperature/supply/process corners are combined with the
# mismatch draw"):
#
#   dc    tb_mc_cp_dc.sp     x design/ `cp` (via the pfd_cp export) -- term 1
#         DC UP/DN current mismatch at 0.9/1.65/2.4 V, N_DC single-instance
#         samples per corner point.
#   sw    tb_mc_cp_switch.sp x the same `cp` -- terms 2/2a
#         Switching-time UP/DN mismatch at Vctrl = 1.65 V (mid-window only --
#         see the record's Methodology field for why a single Vctrl point is
#         used for the STATISTICAL claim), N_SW samples per corner point.
#   pfd   tb_mc_pfd_cp.sp    x design/ `pfd_cp` -- terms 3/4 + PFD-path
#         Residual charge at zero phase error and the local detector gain
#         (dphi = -1n/0/+1n), with the REAL PFD driving -- so PFD-gate
#         mismatch is folded into the same measurement as the charge pump's
#         own, N_PFD samples per corner point.
#   dff   tb_mc_dff_ctq.sp   x design/netlist/dff_tg_3v3.spice -- the
#         divider-retiming-flop contribution (a separate acceptance
#         criterion from the charge-pump terms above): clk->Q delay spread
#         under mismatch, N_DFF invocations x 2 samples each (rise + fall)
#         per corner point.
#
# --- Corner-combined Monte Carlo (#146) -------------------------------------
#
# The first version of this campaign (record 20260731-212614-640560e, still
# present under records/ -- append-only, not touched by this change) ran all
# four sub-campaigns at ONE nominal PVT point, justified there as: "corner
# sensitivity of the MEAN is already the corner-matrix campaigns' job
# (cp-compliance, pfd-deadzone); this campaign's job is the DISPERSION random
# mismatch adds on top." That satisfies sim/README.md's "single nominal point
# ... allowed with justification" rule for a distribution claim, but does NOT
# satisfy the T1/bronze checklist item (#127, item 6) this issue closes, which
# requires Monte Carlo evidence "combined with (not instead of) process
# corners" -- i.e. does mismatch DISPERSION itself vary across the PVT grid,
# not just its mean.
#
# CORNER_POINTS below is a 21-point subset of the repo's 45-point default grid
# (sim/README.md): `typical/27C/3.30V` (nominal) plus ALL 20 VERTICES of the
# process x temperature x supply box -- each of the five MOS bundles
# (`typical`, `ss`, `ff`, `fs`, `sf`) crossed with both temperature extremes
# (-40C, 125C) and both supply extremes (2.97 V, 3.63 V). The 24 points NOT
# visited are all interior on the temperature and/or supply axis (27 C and/or
# 3.30 V) and are bracketed on both sides by visited vertices at the same MOS
# bundle. The MOS-bundle axis is swept in full, with nothing left to
# interpolate across.
#
# --- Why 21 and not the 3 points this grid replaced (issue #597) ------------
#
# #146 ran three points -- `typical/27C/3.30V`, `ss/125C/2.97V`,
# `ff/-40C/3.63V` -- a further cut of the 5-point `WINDOW_CORNERS` set
# `sim/lock-detector/testbench/run.sh` established as a justified reduced-grid
# precedent, itself already a cut of the default grid. #482 then raised the
# per-corner sample counts but left the corner axis at three points, and
# #597's derivation of T1/bronze item 6 (#127) found the corner-combination
# sub-criterion still failing and unowned. #482 offered two routes: widen the
# axis, or ratify the 3-point subset in a decision record. This file takes the
# FIRST route, because on this campaign's own evidence the second route's
# argument cannot be made:
#
#   (1) `fs`/`sf` are structurally the worst case for THIS measurement and
#   were absent. Term 1 is an UP/DN current match between a PMOS source and an
#   NMOS sink. `ss` and `ff` skew both device flavours in the SAME direction,
#   which largely preserves the ratio the metric measures; `fs` and `sf` skew
#   them in OPPOSITE directions, which attacks it directly. That is not a
#   hypothesis about this repo -- `sim/cp-compliance`'s switching bench already
#   binds at `fs`/125C/3.63V (worst-corner `wskew` asymmetry 3.68 fC, the
#   figure `spec/pll.md`'s reference-spur derivation consumes), and
#   `sim/lock-window-sizing`'s two window edges bind at `fs` and `ss`
#   (sim/README.md's own "Default corner matrix" section cites this as the
#   reason a subset's worst case is not a default-grid worst case). A 3-point
#   tt/ss/ff subset therefore could not be claimed to bound the dispersion the
#   other 42 points would show, and a decision record asserting otherwise
#   would have been ratifying a subset because the grid is expensive rather
#   than because the subset bounds the quantity.
#
#   (2) The temp/supply axis was sampled on ONE diagonal only. The 3-point set
#   visited (125C, 2.97V) and (-40C, 3.63V) -- hot/low and cold/high -- and
#   never the anti-diagonal (-40C, 2.97V) or (125C, 3.63V). Mismatch
#   dispersion in a current mirror scales with `gm/I * sigma(Vth)`, which is
#   largest where the devices have the least overdrive: cold AND low-supply.
#   That vertex was exactly the one the diagonal omitted, so the old grid could
#   not even claim to bracket its own two axes.
#
# The full 45-point grid is still not run, and the cost analysis below is still
# why. What changed is that the 21 points now run are the grid's VERTICES
# rather than an interior diagonal, which is a coverage claim that can be
# stated without asserting anything the campaign has not measured: every MOS
# bundle appears, both ends of both continuous axes appear at every bundle, and
# the 24 omitted points sit between measured ones on those axes. The per-corner
# breakdown table in the minted record is what a reader checks that claim
# against -- if an interior point were to bind, it would have to do so
# non-monotonically between two measured vertices, and the table shows the
# behaviour along each axis rather than asserting it.
#
# Cost, re-measured for this grid on this build host (isolated invocations,
# `OMP_NUM_THREADS=1` applied, host load average ~12 of 18 cores): dc 1.2 s,
# sw 30 s, pfd 57 s (three sequential transients per seed), dff 2.3 s. The
# lever that made 21 affordable where #146 judged even 5 unaffordable is the
# `OMP_NUM_THREADS=1` fix (1) below, whose ~44x measured effect was found
# DURING #146's build and so could not be priced into that build's own grid
# decision. THE 21-POINT RUN WAS THEN TIMED END TO END rather than extrapolated
# from those per-invocation figures, because #146's finding (2) below says a
# shared host's wall clock does not extrapolate: at `SIM_JOBS=16` on 18 cores,
# 3864 invocations across the 21 corners took **2 h 20 min** of wall clock,
# throughout which the host's load average -- mostly other tenants -- ranged
# from 23 to 54, and 17 individual ngspice processes were SIGKILLed by the OS
# under memory pressure and recovered by `simenv_run_deck_retried`'s retry (no
# sample was lost; the per-corner row counts were asserted complete at the end,
# as they always are). Per-corner wall clock ranged from about 6 to 13 minutes
# depending on what else was running. The full 45-point grid at these same
# per-corner sample counts would be roughly 2.1x that -- still a handful of
# hours rather than the 45x the paragraph below was written against, since that
# paragraph priced 45 corners at the ORIGINAL N_PFD=40. So the honest statement
# after this run is NOT "45 is impossible": it is that 45 points buys 24 more
# interior points on axes this grid already brackets at both ends, which is a
# poor use of the next 2 hours compared with the gaps named in the record's
# Methodology field. That is a different argument from #146's, and it is the
# one this grid rests on.
#
# The 5-point candidate grid was found impractical during #146's own
# build, for reasons worth recording in full since both were only discovered
# empirically, not predictable from first principles:
#
#   (1) ngspice-46 on this repo's build host is compiled with OpenMP-parallel
#   BSIM model evaluation, so every `ngspice -b` invocation spawns several OS
#   threads on its own, INDEPENDENT of this script's own
#   `xargs -P $(simenv_jobs)` process-level fan-out -- running `simenv_jobs()`
#   (8 on this host) ngspice PROCESSES in parallel, each ALSO internally
#   multi-threaded, oversubscribed the host's 8 physical cores several times
#   over purely from self-contention (measured: one `tb_mc_cp_switch.sp`
#   invocation took 7m48s wall clock with ngspice's default threading vs.
#   10.7s wall clock -- ~44x faster -- with `OMP_NUM_THREADS=1`, for
#   essentially the same total CPU-seconds; see this file's
#   `export OMP_NUM_THREADS=1` below).
#
#   (2) Even with that fix, this build host is ALSO shared with other repos'
#   concurrent agent campaigns (sim/README.md's oversubscription note) whose
#   load is outside this campaign's control -- observed swinging the host
#   load average between ~4 and ~98 (on 8 cores) over the course of #146's own
#   build, and, more strikingly, making individual invocation wall-clock time
#   itself wildly non-reproducible: the SAME isolated (no self-contention)
#   `tb_mc_cp_switch.sp` invocation, run three separate times during this
#   build with no change other than ambient host load, measured 10.7s, 1m40s,
#   and 57 min wall clock. A campaign whose per-invocation cost can swing over
#   ~300x depending on what ELSE is running on the shared host cannot budget a
#   fixed sample count against a fixed wall-clock target the way it could on a
#   dedicated host.
#
# Given both findings, three independent levers were pulled together in #146 to
# keep total wall clock bounded and completion realistic on a host whose OTHER
# tenants cannot be controlled from here: the `OMP_NUM_THREADS=1` fix (1),
# cutting the corner grid from 5 to 3 points (dropping `ss/-40C/3.63V` and
# `ff/125C/2.97V`, the two "off-diagonal" process/temp-supply crossings), and
# cutting the expensive sub-campaigns' per-corner sample counts (below).
# ISSUE #597 REVERSED THE SECOND OF THOSE THREE and widened the axis past even
# the 5-point candidate, to the 21-point vertex set above -- see "Why 21 and not
# the 3 points this grid replaced" for the reasoning and the re-measured cost.
# Finding (2) above still holds and is still why the grid is 21 points and not
# 45: what changed is that lever (1)'s ~44x, discovered mid-#146 and therefore
# unavailable to that build's own sizing decision, moved the affordable corner
# count by roughly an order of magnitude.
#
# Per-corner sample counts are still SMALLER than the nominal-only record's
# (N_DC=200, N_SW=40, N_PFD=40, N_DFF=50 there), but were RAISED from #146's
# original N_DC=20/N_SW=2/N_PFD=2/N_DFF=10 to N_DC=100/N_SW=16/N_PFD=16/N_DFF=20
# PER CORNER (issue #482) once direct timing on this build host (`--one-sw`/
# `--one-pfd` isolated invocations, ~21s/~26s respectively with the
# `OMP_NUM_THREADS=1` fix already applied) showed the ORIGINAL n=2/corner for
# sw/pfd was the cheaper of the two remaining item-6 gaps to close, not a
# wall-clock necessity in its own right: the FULL raised campaign (below)
# measured well under the ~44x-slower unfixed baseline this file's earlier
# comment describes. n=2/corner was "deliberately thin" -- thin enough that a
# term binding the budget verdict at a 2.3% relative margin (term 1, see
# design/README.md's table) could not be told apart from sampling noise at
# that n. n=16 (sw/pfd) and n=100 (dc, cheap enough to raise further almost
# for free) do not reach the nominal-only record's own per-point n, but they
# are a real, measured improvement, not a re-assertion of the same thin
# sample at a later date. The COMBINED n pooled across every corner is
# reported alongside the per-corner breakdown, which is what the binding
# worst-corner verdict actually uses. (That pooled n was a fraction of the
# nominal-only record's own n at 3 corners; at #597's 21 corners it exceeds it
# several times over -- but pooling across corners is still NOT the figure the
# verdict uses, for the reason the dff bullet in the minted record gives:
# pooling mixes corner-to-corner systematic spread into a within-corner
# mismatch sigma.)
#
# THE RAISE CHANGED A VERDICT, which is the reason to record it here rather
# than only in one record's prose. At n=20/corner term 1 measured 11.7211%
# against design/README.md's then-current +-12% budget -- a PASS by a 2.3%
# relative margin. At n=100/corner, same corner grid, same seeds-from-1
# convention, same decks, it measures 13.2172% -- which was a FAIL against
# that budget, by 4.4 standard errors of the mean. The n=20 PASS was inside
# its own sampling noise and did not survive contact with a sample large
# enough to resolve it. This script did NOT widen the budget in response:
# design/README.md states that the resolution of a budget the statistics do
# not fit is a decision record, so the FAIL was emitted as a FAIL and the
# record named the decision record as the next step. Do not "fix" the sample
# size by lowering N_DC.
#
# THE STATISTIC ITSELF WAS ALSO MISLABELLED, AND FIXING THAT MOVES TERM 1'S
# NUMBER UP (#487). Term 1 used to be reported as `mean(|x|) + 3*sd(|x|)` on
# samples folded to their absolute value, while the record, the per-corner
# table and design/README.md all called that figure `|mean| + 3*sigma` (and
# the budget column "3 sigma"). Folding merges the distribution's two tails
# before the tail is formed, which makes the figure SMALLER, not larger: on
# the committed n=100/corner samples of `20260923-095854-1655e11` the binding
# corner is 13.2172% folded and 17.4798% signed. This script now reports both
# under honest names and takes the VERDICT on the signed `|mean| + 3*sigma`,
# which is the statistic design/README.md's budget column describes and the
# one DR-018 §Decision explicitly pre-authorised ("checks the same +-20%,
# without a further record"). Re-derive either figure from any committed
# campaign with `./run.sh --restat <record-id>` -- no simulation needed. Do
# not swap back to the folded form to buy margin.
#
# THE BUDGET HAS SINCE MOVED, AND THAT IS WHY THE VERDICT WILL FLIP (#483).
# DR-018 re-derived term 1's budget from the ratified <= -55 dBc
# reference-spur line -- via the PFD-reset-overlap mechanism that turns
# current mismatch into ripple charge, dQ1 = m * Icp * T_ov -- and widened it
# from +-12% to +-20% (TERM1_BUDGET_PCT below is the single place that number
# lives now). The next run of this campaign will therefore report PASS on the
# SAME design and the SAME measurement that the committed
# `20260923-095854-1655e11` record reports FAIL on. That is a budget change,
# not a measurement change; sim/ is append-only, so that record keeps its FAIL
# and its bytes, and anyone comparing the two must read the difference that
# way. Do not "reconcile" them by editing the older record.
#
# Deliberately does NOT attempt a closed-loop reference-spur check: the
# acceptance criteria (#15) ask for one using #12's lock-time/output-range
# bench specifically, "not a separate ad hoc closed-loop harness" -- and #12
# has landed on `main` since the original record (`sim/lock-time/`,
# `sim/output-range/` now exist), but wiring THAT check is a separate,
# already-tracked gap (see #127's checklist), not this issue's scope (#146 is
# specifically the MC-combined-with-corners + VCO band-select mirror gap).
# This record continues to state the gap honestly rather than fabricating a
# closed-loop number as a side effect of the corner-grid extension.
#
# --- Erratum: the `# switches:` line of the CSVs already committed (#601) ----
#
# Every CSV this script writes opens with `simenv_provenance`'s header, so the
# table stays self-describing away from its record. Until #601 that function
# hardcoded one switches line with no parameter --
#
#   # switches: design.ngspice defaults (sw_stat_global=0, sw_stat_mismatch=0
#   #           -> nominal skew, no Monte Carlo)
#
# -- which is the exact opposite of what this campaign does: SWITCHES_NOTE
# below records the `sw_stat_mismatch=1` this script passes on every ngspice
# invocation, and the record's own Environment provenance field has said so
# correctly since #15 (simenv_env_block grew the override parameter;
# simenv_provenance did not). The twelve CSVs minted before the fix therefore
# carry a header that contradicts their own record:
#
#   corners/20260731-212614-640560e/{mc_cp_dc,mc_cp_switch,mc_pfd_cp,mc_dff_ctq}.csv
#   corners/20260817-135712-0e9cfc9/{mc_cp_dc,mc_cp_switch,mc_pfd_cp,mc_dff_ctq}.csv
#   corners/20260923-095854-1655e11/{mc_cp_dc,mc_cp_switch,mc_pfd_cp,mc_dff_ctq}.csv
#
# Those bytes are NOT edited and neither are the records beside them: `sim/` is
# append-only evidence and sim/README.md forbids rewriting a committed record
# even to add a true, helpful pointer. The correction is made forward, here, in
# the live testbench artifact -- the same disposition
# sim/lock-window-trim/testbench/tb.json uses for its own stale-figure erratum.
# For those twelve files the record's Environment provenance field is
# authoritative and the CSV's `# switches:` line is a harness default that was
# never true of the run; every CSV minted from this script after #601 states
# the switches the run actually used.
#
# Nothing computed is affected: no figure in any record, and no check script,
# parses that line -- simenv_datarows drops every `#` comment before the data
# is read.
#
# Usage:
#   ./run.sh                 # full corner-combined campaign -> mints a records/<id>.md
#   ./run.sh --check         # a handful of samples per sub-campaign at nominal, to stdout
#   ./run.sh --restat <id>   # re-derive the statistics of an ALREADY-COMMITTED
#                            # campaign from corners/<record-id>/*.csv and print
#                            # them. Reads committed evidence only: no ngspice,
#                            # no netlist export, and no record is minted.
#   SIM_JOBS=8 ./run.sh      # cap parallelism
#   N_DC=.. N_SW=.. N_PFD=.. N_DFF=..   override PER-CORNER sample counts

set -euo pipefail

# --- Host oversubscription fix (#146) ---------------------------------------
#
# ngspice-46 on this repo's build host is compiled with OpenMP-parallel BSIM
# model evaluation: EVERY `ngspice -b` invocation spawns ~5-6 OS threads on
# its own (confirmed via `pstree -p` on a running invocation), independent of
# `simenv_jobs`'s process-level fan-out. Running `simenv_jobs()` (8 on this
# host) PROCESSES in parallel, each ALSO internally OpenMP-threaded, meant the
# `sw`/`pfd` sub-campaigns (the two with a genuinely stiff `cp_dumpbuf`-loaded
# transient) were oversubscribing the host's 8 physical cores by roughly 6x
# from self-contention alone, on top of whatever other campaigns/repos share
# the host (sim/README.md's oversubscription note). Direct measurement during
# #146: one `tb_mc_cp_switch.sp` invocation, run in isolation, took 7m48s
# real (46m42s user -- i.e. ~6 threads averaging ~85% each) with ngspice's
# default threading; the SAME invocation with `OMP_NUM_THREADS=1` took 10.7s
# real (~44x faster) for 1m04s of user time -- confirming the wall-clock cost
# was self-inflicted thread oversubscription, not genuine compute. Pinning to
# one thread per ngspice PROCESS and letting `simenv_jobs` provide the
# parallelism at the process level (the level `xargs -P` below already
# fans out at) is the correct division of the host's 8 cores. #241
# centralized the DETECTION half of this fix into
# sim/lib/simenv.sh::simenv_apply_omp_pin -- called below, right after
# sourcing that file -- while keeping this campaign's own OPT-IN call (not a
# changed default inside simenv.sh itself), for the same "don't silently
# change every other campaign's behavior" reason the original fix stated.
# An explicit OMP_NUM_THREADS in the environment still always wins.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP="$(cd "${HERE}/.." && pwd)"
REPO="$(cd "${EXP}/../.." && pwd)"
# shellcheck source=../../lib/simenv.sh
. "${HERE}/../../lib/simenv.sh"
simenv_apply_omp_pin

DECK_DC="${HERE}/tb_mc_cp_dc.sp"
DECK_SW="${HERE}/tb_mc_cp_switch.sp"
DECK_PFD="${HERE}/tb_mc_pfd_cp.sp"
DECK_DFF="${HERE}/tb_mc_dff_ctq.sp"
WORK="${EXP}/work"
NETLIST="${WORK}/dut.spice"
DFF_NETLIST_SRC="${REPO}/design/netlist/dff_tg_3v3.spice"
DUT_DFF="${WORK}/dut_dff.sp"

# Corner point for a single invocation (--one-* entry points and --check).
# Overridable per-invocation via env so the corner loop below can spawn one
# fresh bash process per (corner, sample) through xargs without editing this
# file per point.
CORNER="${SIM_CORNER:-typical}"
TEMP="${SIM_TEMP:-27}"
VDD="${SIM_VDD:-3.30}"
# Mid-window Vctrl, matching pfd-deadzone / design/README.md's term 3/4.
VCTRL_MID=1.65

# Per-corner sample counts. dc/dff are cheap (<2 s/invocation, confirmed
# during #146's build: 20 dc samples completed in 17 s even under today's
# heavy host contention); sw/pfd are expensive (cp_dumpbuf's stiff control
# node) AND -- discovered during #146's own build -- their wall-clock time
# varies wildly under shared-host contention (the SAME isolated `sw`
# invocation measured 10.7 s, 1m40s, and 57 min at different points during
# this campaign's own build, with no change other than ambient host load).
# The dominant cost of this campaign is per-invocation WALL-CLOCK LATENCY
# under contention, not sample count: sw/pfd invocations already run at full
# `simenv_jobs` parallelism (8 on this host), so wall clock per BATCH is set
# by the slowest invocation in it, not the sum -- which means raising N only
# multiplies the number of BATCHES (ceil(N / simenv_jobs)), not the raw
# invocation count's wall-clock cost. #146 originally kept N_SW=N_PFD=2 (one
# batch, whatever that batch's slowest invocation happened to cost) --
# "deliberately too thin ... to assert a tight per-corner sigma" by that
# record's own admission, and specifically what issue #482 flagged as the
# thinner and cheaper of item 6's two remaining gaps to close. #482 raised
# N_SW/N_PFD to 16 (two batches instead of one, roughly 2x this campaign's
# per-corner sw/pfd wall clock, not 8x) and N_DC to 100 (dc is cheap enough,
# <1s/invocation even under contention, that raising it costs single-digit
# seconds per corner). N_DFF was raised to 20 for the same cheap-enough
# reason, tightening the divider-retiming-flop contribution's own worst-case
# estimate. This still leans on the corner-vs-sample-count tradeoff (the
# per-corner breakdown is tighter than #146's but still short of the
# nominal-only record's own per-point n; the pooled, all-corner statistic
# remains the tighter combined-distribution estimate) -- it does not attempt
# the full 45-point grid, which the header comment's cost analysis above
# still rules out.
N_DC="${N_DC:-100}"
N_SW="${N_SW:-16}"
N_PFD="${N_PFD:-16}"
N_DFF="${N_DFF:-20}"

DC_HEADER="corner,seed,vctrl_v,iup_a,idn_a,mism_pct"
SW_HEADER="corner,seed,vctrl_v,wskew_s"
PFD_HEADER="corner,seed,qnet0_c,qplus_c,qminus_c,kd_wide_a,t_offset_s"
DFF_HEADER="corner,seed,tcq_r_s,tcq_f_s"

# The `# switches:` line of every CSV this script writes (#601). Passed to
# simenv_provenance as its optional fifth argument, in one place so the four
# sub-campaigns cannot drift apart; the prose counterpart is the
# simenv_env_block switches-note in the record body below, and the fact it
# states is the `sw_stat_mismatch=1` every ngspice invocation in this file
# passes. Without it simenv_provenance emits its design.ngspice-default
# wording, which for this campaign says the opposite of what ran -- see the
# erratum in this file's header comment for the CSVs that shipped that way.
SWITCHES_NOTE="design.ngspice defaults OVERRIDDEN by this campaign (sw_stat_global=0, sw_stat_mismatch=1 -> mismatch-only Monte Carlo, .option rndseed set per sample)"

# simenv_run_deck_retried (3-attempt retry wrapper around simenv_run_deck,
# #146 host-flakiness mitigation) is hoisted to sim/lib/simenv.sh -- #184.
# Every simenv_run_deck call in this file goes through it rather than being
# called directly; see that function's comment there for the full
# investigation.

# ===========================================================================
# dc: tb_mc_cp_dc.sp -- term 1 (DC UP/DN current mismatch)
# ===========================================================================
run_dc() {
  local seed="$1" sfile="$2"
  local ctag="${CORNER}_${TEMP}c_${VDD}v"
  local tag="dc_${ctag}_seed$(printf '%03d' "${seed}")"
  simenv_stage_netlist "${WORK}/${tag}" "${NETLIST}"
  simenv_run_deck_retried "${DECK_DC}" "${WORK}" "${tag}" "${CORNER}" "${TEMP}" \
    "vsup=${VDD}" "sw_stat_mismatch=1" "rndseed=${seed}" >/dev/null
  local log="${WORK}/${tag}/ngspice.log"
  local pt line iup idn
  for pt in "LO:0.9" "MID:1.65" "HI:2.4"; do
    local tag2="${pt%%:*}" v="${pt##*:}"
    line=$(grep "^MCDC_${tag2} " "${log}" | tail -1)
    [ -n "${line}" ] || { echo "ERROR: missing MCDC_${tag2} for corner=${ctag} seed=${seed}" >&2; return 1; }
    iup=$(echo "${line}" | sed -n 's/.*iup=\([^ ]*\).*/\1/p')
    idn=$(echo "${line}" | sed -n 's/.*idn=\([^ ]*\).*/\1/p')
    awk -v c="${ctag}" -v s="${seed}" -v v="${v}" -v iu="${iup}" -v id="${idn}" \
      'BEGIN { printf "%s,%s,%s,%.6g,%.6g,%.4f\n", c, s, v, iu, id, 100*(iu-id)/(0.5*(iu+id)) }' >>"${sfile}"
  done
}

# ===========================================================================
# sw: tb_mc_cp_switch.sp -- terms 2/2a (switching-time UP/DN mismatch)
# ===========================================================================
run_sw() {
  local seed="$1" sfile="$2"
  local ctag="${CORNER}_${TEMP}c_${VDD}v"
  local tag="sw_${ctag}_seed$(printf '%03d' "${seed}")"
  simenv_stage_netlist "${WORK}/${tag}" "${NETLIST}"
  simenv_run_deck_retried "${DECK_SW}" "${WORK}" "${tag}" "${CORNER}" "${TEMP}" \
    "vsup=${VDD}" "vctrl=${VCTRL_MID}" "sw_stat_mismatch=1" "rndseed=${seed}" >/dev/null
  local log="${WORK}/${tag}/ngspice.log" line wskew
  line=$(grep "^MCSW " "${log}" | tail -1)
  [ -n "${line}" ] || { echo "ERROR: missing MCSW for corner=${ctag} seed=${seed}" >&2; return 1; }
  wskew=$(echo "${line}" | sed -n 's/.*wskew=\([^ ]*\).*/\1/p')
  printf '%s,%s,%s,%s\n' "${ctag}" "${seed}" "${VCTRL_MID}" "${wskew}" >>"${sfile}"
}

# ===========================================================================
# pfd: tb_mc_pfd_cp.sp -- terms 3/4 (residual charge / static phase offset)
# ===========================================================================
run_pfd() {
  local seed="$1" sfile="$2"
  local ctag="${CORNER}_${TEMP}c_${VDD}v"
  local sseed dphi qnet0="" qplus="" qminus=""
  sseed=$(printf '%03d' "${seed}")
  for dphi in -1n 0 1n; do
    local dsuf="d${dphi}"; dsuf="${dsuf//./p}"; dsuf="${dsuf//-/m}"
    local dtag="pfd_${ctag}_seed${sseed}_${dsuf}"
    simenv_stage_netlist "${WORK}/${dtag}" "${NETLIST}"
    simenv_run_deck_retried "${DECK_PFD}" "${WORK}" "${dtag}" "${CORNER}" "${TEMP}" \
      "vsup=${VDD}" "dphi=${dphi}" "sw_stat_mismatch=1" "rndseed=${seed}" >/dev/null
    local log="${WORK}/${dtag}/ngspice.log" line q
    line=$(grep "^MCPFD " "${log}" | tail -1)
    [ -n "${line}" ] || { echo "ERROR: missing MCPFD for corner=${ctag} seed=${seed} dphi=${dphi}" >&2; return 1; }
    q=$(echo "${line}" | sed -n 's/.*qnet=\([^ ]*\).*/\1/p')
    case "${dphi}" in
      0) qnet0="${q}" ;;
      1n) qplus="${q}" ;;
      -1n) qminus="${q}" ;;
    esac
  done
  awk -v c="${ctag}" -v s="${seed}" -v q0="${qnet0}" -v qp="${qplus}" -v qm="${qminus}" '
    BEGIN {
      kd = (qp - qm) / 2e-9
      toff = q0 / kd
      printf "%s,%s,%.6g,%.6g,%.6g,%.6g,%.6g\n", c, s, q0, qp, qm, kd, toff
    }' >>"${sfile}"
}

# ===========================================================================
# dff: tb_mc_dff_ctq.sp -- divider-retiming clk->Q spread
# ===========================================================================
run_dff() {
  local seed="$1" sfile="$2"
  local ctag="${CORNER}_${TEMP}c_${VDD}v"
  local tag="dff_${ctag}_seed$(printf '%03d' "${seed}")"
  simenv_run_deck_retried "${DUT_DFF}" "${WORK}" "${tag}" "${CORNER}" "${TEMP}" \
    "vsup=${VDD}" "sw_stat_mismatch=1" "rndseed=${seed}" >/dev/null
  local log="${WORK}/${tag}/ngspice.log" tcq_r tcq_f
  tcq_r=$(simenv_meas "${log}" tcq_r)
  tcq_f=$(simenv_meas "${log}" tcq_f)
  printf '%s,%s,%s,%s\n' "${ctag}" "${seed}" "${tcq_r}" "${tcq_f}" >>"${sfile}"
}

# Corner grid this campaign combines MC with -- see the header comment's
# "Corner-combined Monte Carlo" section for why this 21-point vertex set (all
# 20 vertices of the process x temperature x supply box, plus nominal) and not
# the 3-point diagonal subset it replaced or the full 45-point default grid.
# bundle/temp/vdd. Defined up here, ahead of the entry points, because
# `--restat` (below) re-derives the per-corner breakdown of an
# already-committed campaign and needs the same corner list the run used.
CORNER_POINTS=(
  "typical 27 3.30"
  "typical -40 2.97"
  "typical -40 3.63"
  "typical 125 2.97"
  "typical 125 3.63"
  "ss -40 2.97"
  "ss -40 3.63"
  "ss 125 2.97"
  "ss 125 3.63"
  "ff -40 2.97"
  "ff -40 3.63"
  "ff 125 2.97"
  "ff 125 3.63"
  "fs -40 2.97"
  "fs -40 3.63"
  "fs 125 2.97"
  "fs 125 3.63"
  "sf -40 2.97"
  "sf -40 3.63"
  "sf 125 2.97"
  "sf 125 3.63"
)
NUM_CORNERS=${#CORNER_POINTS[@]}

# Markdown rendering of the grid above, plus the count of non-nominal points,
# built from the SAME array the run loop and `--restat` iterate. The minted
# record interpolates these rather than carrying a hand-written corner list, so
# the record's "Corner matrix run" field cannot drift from the points that
# actually ran (which is exactly how the 3-point list survived two records).
CORNER_LIST_MD=""
NUM_VERTICES=0
for __point in "${CORNER_POINTS[@]}"; do
  read -r __pc __pt __pv <<<"${__point}"
  if [ "${__pt}" = "27" ] && [ "${__pv}" = "3.30" ]; then
    CORNER_LIST_MD="${CORNER_LIST_MD}  - \`${__pc}/${__pt}C/${__pv}V\` (nominal)
"
  else
    NUM_VERTICES=$(( NUM_VERTICES + 1 ))
    CORNER_LIST_MD="${CORNER_LIST_MD}  - \`${__pc}/${__pt}C/${__pv}V\`
"
  fi
done
unset __point __pc __pt __pv

# ===========================================================================
# Statistics: mean, sample stddev (N-1), |mean|+3sigma
# ===========================================================================
# Read back from the CSVs the run just wrote -- or, under `--restat`, from an
# ALREADY-COMMITTED campaign's CSVs -- so the record text cannot drift from
# the data. Data rows are neither the leading `simenv_provenance` `#` comment
# block nor the CSV header row -- strip both before handing the column to awk.
# (simenv_datarows / simenv_stats_from_values live in sim/lib/simenv.sh --
# #183.)
#
# --- WHICH statistic, and why term 1 reports two of them (issue #487) ------
#
# Terms 2/2a/3/4 are reduced from SIGNED samples with no folding: `stats()`
# takes the column as it stands and `sig3()` forms `|mean| + 3*sigma` -- the
# 3-sigma tail on the worse side of a systematic mean, which is the correct
# worst-case magnitude for a signed error checked against a two-sided budget,
# and is exactly what design/README.md's budget column says it is checked
# against. Those three terms were re-checked for the folding defect below and
# are clean: `stats`/`stats_corner` never take an absolute value.
#
# Term 1 was the exception, because its per-sample reduction is a WORST-OF-
# THREE-Vctrl-POINTS selection (`cp-compliance`'s "worst point in window"
# convention). Selecting the worst point requires comparing MAGNITUDES -- and
# the campaign then discarded the sign and reported `mean(|x|) + 3*sd(|x|)` of
# the surviving magnitudes, while the record, the per-corner table and
# design/README.md all called that figure `|mean|+3sigma` / "3 sigma". Those
# are not the same statistic, and the folded one is the LESS conservative:
# folding mixes the distribution's two tails into one pile, shrinking both the
# mean and the sd. On record `20260923-095854-1655e11`'s committed n=100/corner
# samples the binding corner (`ff`/-40C/3.63V) reads 13.2172% folded against
# 17.4798% signed -- the distribution's own 3-sigma tail is ~1.3x LARGER than
# the number that was being quoted as "3 sigma" -- and 13.2172% is not a clean
# quantile of anything either (~98.5th percentile of the sample, where a
# 3-sigma tail sits at 99.87th).
#
# So both are computed and both are reported, under names that say what they
# are, and the VERDICT is taken on the SIGNED form -- the conservative one.
# DR-018 priced term 1's +-20% budget against both readings explicitly and
# pre-authorised this in its Decision section: "A future campaign that reports
# the signed |mean| + 3*sigma form instead -- which would be the more honest
# statistic, and is filed as #487 -- checks the same +-20%, without a further
# record". This changes the reported number, not the budget, and it changes it
# UPWARDS. Do not swap back to the folded form to buy margin.

# Pooled stats across ALL corners for a given file/field.
stats() {
  # stats <file> <field> -> "mean sd n"
  simenv_datarows "$1" | awk -F, -v f="$2" '{print $f}' | simenv_stats_from_values
}

# Per-corner stats for a given file/field/corner tag.
stats_corner() {
  # stats_corner <file> <field> <corner_tag> -> "mean sd n"
  simenv_datarows "$1" | awk -F, -v f="$2" -v c="$3" '$1==c {print $f}' | simenv_stats_from_values
}

# Term 1's per-(corner,seed) reduction: the worst-MAGNITUDE of the 3 Vctrl
# points. Selection is always by magnitude (that is what "worst point in the
# window" means); what differs is what gets printed for the selected point:
#
#   dc_worst abs    [corner] -> the magnitude      (the FOLDED series)
#   dc_worst signed [corner] -> the signed value   (the SIGNED series)
#
# An empty/absent corner argument pools all corners. See the issue-#487 note
# above for why both series exist and which one carries the verdict.
dc_worst() {
  local mode="$1" corner="${2:-}"
  simenv_datarows "${OUT_DC}" | awk -F, -v m="${mode}" -v c="${corner}" '
    c != "" && $1 != c { next }
    { a = ($6<0 ? -$6 : $6); s = $1 SUBSEP $2
      if (!(s in seen) || a > worst[s]) { worst[s] = a; signed[s] = $6; seen[s] = 1 } }
    END { for (s in worst) print (m == "signed") ? signed[s] : worst[s] }'
}

# |mean| + 3*sd. For the folded series the mean is non-negative by
# construction, so the same helper also gives `mean(|x|) + 3*sd(|x|)`.
sig3() { awk -v m="$1" -v s="$2" 'BEGIN{printf "%.6g", (m<0?-m:m)+3*s}'; }

# Term 1's budget, in percent, and the ONLY place it is written down in this
# script. DR-018 (#483) sets it at 20%, derived from the ratified <= -55 dBc
# reference-spur line rather than from headroom over the systematic value; it
# was 12% before that record. design/README.md's "Up/down mismatch budget"
# table is the human-readable copy and must agree with this constant.
TERM1_BUDGET_PCT=20

verdict() { awk -v v="$1" -v b="$2" 'BEGIN{print (v<=b)?"PASS":"FAIL"}'; }

# compute_term_stats: reads ${OUT_DC}/${OUT_SW}/${OUT_PFD}/${OUT_DFF} and
# CORNER_POINTS; sets every DC_*/SW_*/PFD_*/DFF_*/WORST_*/V* global the record
# template and the stdout summary interpolate. Called on the normal run path
# right after the CSVs are written, and by `--restat` against a committed
# campaign's CSVs (no ngspice, no netlist export).
compute_term_stats() {
  local point pc pt pv ctag
  local c_dc c_dc_m c_dc_s c_dc_n c_dc_3s
  local c_dcs c_dcs_m c_dcs_s c_dcs_n c_dcs_3s
  local c_sw c_sw_m c_sw_s c_sw_n c_sw_3s
  local c_pfdq c_pfdq_m c_pfdq_s c_pfdq_3s
  local c_pfdt c_pfdt_m c_pfdt_s c_pfdt_n c_pfdt_3s
  local c_dffr c_dffr_m c_dffr_s c_dffr_n c_dffr_3s
  local c_dfff c_dfff_m c_dfff_s c_dfff_3s c_dff_3s c_dff_sig3 c_dff_mean

  # Term 1, pooled: folded (`mean(|x|)+3*sd(|x|)`) and signed (`|mean|+3sigma`).
  DC_N=$(dc_worst abs | wc -l | tr -d ' ')
  DC_STATS=$(dc_worst abs | simenv_stats_from_values)
  DC_MEAN=$(echo "${DC_STATS}" | awk '{print $1}'); DC_SD=$(echo "${DC_STATS}" | awk '{print $2}')
  DC_S_STATS=$(dc_worst signed | simenv_stats_from_values)
  DC_S_MEAN=$(echo "${DC_S_STATS}" | awk '{print $1}'); DC_S_SD=$(echo "${DC_S_STATS}" | awk '{print $2}')

  SW_STATS=$(stats "${OUT_SW}" 4)
  SW_MEAN=$(echo "${SW_STATS}" | awk '{print $1}'); SW_SD=$(echo "${SW_STATS}" | awk '{print $2}')

  PFD_Q_STATS=$(stats "${OUT_PFD}" 3)
  PFD_Q_MEAN=$(echo "${PFD_Q_STATS}" | awk '{print $1}'); PFD_Q_SD=$(echo "${PFD_Q_STATS}" | awk '{print $2}')
  PFD_T_STATS=$(stats "${OUT_PFD}" 7)
  PFD_T_MEAN=$(echo "${PFD_T_STATS}" | awk '{print $1}'); PFD_T_SD=$(echo "${PFD_T_STATS}" | awk '{print $2}')

  DFF_R_STATS=$(stats "${OUT_DFF}" 3)
  DFF_R_MEAN=$(echo "${DFF_R_STATS}" | awk '{print $1}'); DFF_R_SD=$(echo "${DFF_R_STATS}" | awk '{print $2}')
  DFF_F_STATS=$(stats "${OUT_DFF}" 4)
  DFF_F_MEAN=$(echo "${DFF_F_STATS}" | awk '{print $1}'); DFF_F_SD=$(echo "${DFF_F_STATS}" | awk '{print $2}')

  DC_3S=$(sig3 "${DC_MEAN}" "${DC_SD}")
  DC_S_3S=$(sig3 "${DC_S_MEAN}" "${DC_S_SD}")
  SW_3S=$(sig3 "${SW_MEAN}" "${SW_SD}")
  PFD_Q_3S=$(sig3 "${PFD_Q_MEAN}" "${PFD_Q_SD}")
  PFD_T_3S=$(sig3 "${PFD_T_MEAN}" "${PFD_T_SD}")
  DFF_R_3S=$(sig3 "${DFF_R_MEAN}" "${DFF_R_SD}")
  DFF_F_3S=$(sig3 "${DFF_F_MEAN}" "${DFF_F_SD}")

  # ------------------------------------------------------------------------
  # Per-corner breakdown table + worst-across-corners (the number the verdict
  # uses -- corner-combined MC's whole point is that the worst corner, not the
  # pooled or nominal-only figure, is what has to fit the budget).
  # ------------------------------------------------------------------------
  PERCORNER_ROWS=""
  WORST_DC_3S=0; WORST_DCS_3S=0
  WORST_SW_3S=0; WORST_PFDQ_3S=0; WORST_PFDT_3S=0; WORST_DFF_3S=0
  WORST_SW_CORNER=""; WORST_PFDQ_CORNER=""; WORST_PFDT_CORNER=""
  # Term 1's binding worst-corner sample also gets its own standard error
  # tracked alongside it (issue #482) -- the verdict table states a PASS/FAIL
  # against a budget, but a margin narrower than a few standard errors is not
  # distinguishable from sampling noise at the sample size actually used, and
  # the record should say so explicitly rather than let a bare percentage imply
  # more precision than the sample size supports. Tracked on the SIGNED series,
  # because that is the series the verdict is taken on (issue #487); the folded
  # series' own binding corner is tracked too, for the figure the record quotes
  # beside it.
  WORST_DCS_MEAN=0; WORST_DCS_SD=0; WORST_DCS_N=0; WORST_DCS_CORNER=""
  WORST_DC_SD=0; WORST_DC_N=0; WORST_DC_CORNER=""
  # Worst-corner MISMATCH-ONLY dispersion for the divider-retiming flop (3sigma
  # with no |mean| term) -- see the in-loop comment below for why this, and not
  # WORST_DFF_3S, is the flop's actual contribution (issue #482).
  WORST_DFF_SIG3=0; WORST_DFF_SIG3_CORNER=""; WORST_DFF_SIG3_MEAN=0; WORST_DFF_SIG3_N=0
  # Span of the flop's per-corner MEAN clk->Q delay across the grid -- the
  # systematic corner-to-corner spread that pooling would fold into a
  # within-corner mismatch sigma. Derived rather than hand-written, because the
  # figure moves with the corner grid (issue #597 widened the grid from 3 points
  # to ${NUM_CORNERS} and the previously hand-written "165 ps to 371 ps" was a
  # 3-point-grid figure).
  DFF_MEAN_MIN=""; DFF_MEAN_MAX=""
  for point in "${CORNER_POINTS[@]}"; do
    read -r pc pt pv <<<"${point}"
    ctag="${pc}_${pt}c_${pv}v"

    c_dc=$(dc_worst abs "${ctag}" | simenv_stats_from_values)
    c_dc_m=$(echo "${c_dc}" | awk '{print $1}'); c_dc_s=$(echo "${c_dc}" | awk '{print $2}'); c_dc_n=$(echo "${c_dc}" | awk '{print $3}')
    c_dc_3s=$(sig3 "${c_dc_m}" "${c_dc_s}")

    c_dcs=$(dc_worst signed "${ctag}" | simenv_stats_from_values)
    c_dcs_m=$(echo "${c_dcs}" | awk '{print $1}'); c_dcs_s=$(echo "${c_dcs}" | awk '{print $2}'); c_dcs_n=$(echo "${c_dcs}" | awk '{print $3}')
    c_dcs_3s=$(sig3 "${c_dcs_m}" "${c_dcs_s}")

    c_sw=$(stats_corner "${OUT_SW}" 4 "${ctag}")
    c_sw_m=$(echo "${c_sw}" | awk '{print $1}'); c_sw_s=$(echo "${c_sw}" | awk '{print $2}'); c_sw_n=$(echo "${c_sw}" | awk '{print $3}')
    c_sw_3s=$(sig3 "${c_sw_m}" "${c_sw_s}")

    c_pfdq=$(stats_corner "${OUT_PFD}" 3 "${ctag}")
    c_pfdq_m=$(echo "${c_pfdq}" | awk '{print $1}'); c_pfdq_s=$(echo "${c_pfdq}" | awk '{print $2}')
    c_pfdq_3s=$(sig3 "${c_pfdq_m}" "${c_pfdq_s}")

    c_pfdt=$(stats_corner "${OUT_PFD}" 7 "${ctag}")
    c_pfdt_m=$(echo "${c_pfdt}" | awk '{print $1}'); c_pfdt_s=$(echo "${c_pfdt}" | awk '{print $2}'); c_pfdt_n=$(echo "${c_pfdt}" | awk '{print $3}')
    c_pfdt_3s=$(sig3 "${c_pfdt_m}" "${c_pfdt_s}")

    c_dffr=$(stats_corner "${OUT_DFF}" 3 "${ctag}")
    c_dffr_m=$(echo "${c_dffr}" | awk '{print $1}'); c_dffr_s=$(echo "${c_dffr}" | awk '{print $2}'); c_dffr_n=$(echo "${c_dffr}" | awk '{print $3}')
    c_dffr_3s=$(sig3 "${c_dffr_m}" "${c_dffr_s}")
    c_dfff=$(stats_corner "${OUT_DFF}" 4 "${ctag}")
    c_dfff_m=$(echo "${c_dfff}" | awk '{print $1}'); c_dfff_s=$(echo "${c_dfff}" | awk '{print $2}')
    c_dfff_3s=$(sig3 "${c_dfff_m}" "${c_dfff_s}")
    c_dff_3s=$(awk -v a="${c_dffr_3s}" -v b="${c_dfff_3s}" 'BEGIN{print (a>b)?a:b}')

    # Mismatch-ONLY dispersion for the flop: 3*sigma with NO |mean| term
    # (issue #482). Terms 1-4's sample mean is itself an ERROR centred near
    # zero, so `|mean|+3sigma` is the right worst-case magnitude for them. The
    # flop's tcq mean is NOT an error -- it is the nominal clk->Q PROPAGATION
    # DELAY, which sim/divider-ratio-dff already sweeps systematically over the
    # full 45-point grid (`sw_stat_mismatch=0`). Quoting `|mean|+3sigma` for
    # this quantity therefore reports the systematic delay with a sliver of
    # mismatch on top -- at this campaign's own worst corner the mean is ~98%
    # of that figure -- and double-counts a delay already measured elsewhere.
    # What THIS campaign uniquely measures for the flop is the dispersion the
    # mismatch draw adds, which is 3*sigma alone.
    c_dff_sig3=$(awk -v a="${c_dffr_s}" -v b="${c_dfff_s}" 'BEGIN{x=(a>b)?a:b; printf "%.6g", 3*x}')
    c_dff_mean=$(awk -v a="${c_dffr_m}" -v b="${c_dfff_m}" 'BEGIN{printf "%.6g", (a>b)?a:b}')
    if awk -v a="${WORST_DFF_SIG3}" -v b="${c_dff_sig3}" 'BEGIN{exit !(b+0>a+0)}'; then
      WORST_DFF_SIG3="${c_dff_sig3}"; WORST_DFF_SIG3_CORNER="${ctag}"
      WORST_DFF_SIG3_MEAN="${c_dff_mean}"; WORST_DFF_SIG3_N="${c_dffr_n}"
    fi
    if [ -z "${DFF_MEAN_MIN}" ] || awk -v a="${DFF_MEAN_MIN}" -v b="${c_dff_mean}" 'BEGIN{exit !(b+0<a+0)}'; then
      DFF_MEAN_MIN="${c_dff_mean}"
    fi
    if [ -z "${DFF_MEAN_MAX}" ] || awk -v a="${DFF_MEAN_MAX}" -v b="${c_dff_mean}" 'BEGIN{exit !(b+0>a+0)}'; then
      DFF_MEAN_MAX="${c_dff_mean}"
    fi

    PERCORNER_ROWS="${PERCORNER_ROWS}  | ${ctag} | ${c_dcs_3s}% (n=${c_dcs_n}) | ${c_dc_3s}% | ${c_sw_3s} s (n=${c_sw_n}) | ${c_pfdq_3s} C | ${c_pfdt_3s} s (n=${c_pfdt_n}) | ${c_dff_sig3} s (mean ${c_dff_mean} s, n=${c_dffr_n}) |
"

    if awk -v a="${WORST_DCS_3S}" -v b="${c_dcs_3s}" 'BEGIN{exit !(b+0>a+0)}'; then
      WORST_DCS_MEAN="${c_dcs_m}"; WORST_DCS_SD="${c_dcs_s}"; WORST_DCS_N="${c_dcs_n}"; WORST_DCS_CORNER="${ctag}"
    fi
    if awk -v a="${WORST_DC_3S}" -v b="${c_dc_3s}" 'BEGIN{exit !(b+0>a+0)}'; then
      WORST_DC_SD="${c_dc_s}"; WORST_DC_N="${c_dc_n}"; WORST_DC_CORNER="${ctag}"
    fi
    # Terms 2/2a, 3 and 4 track WHICH corner binds them as well as the value
    # (issue #597). At 3 corners all four terms happened to bind at the same
    # point and the record could name it once; at ${NUM_CORNERS} they do not,
    # and a re-grading table that names a corner has to read it from the data
    # rather than have it written in by hand.
    if awk -v a="${WORST_SW_3S}" -v b="${c_sw_3s}" 'BEGIN{exit !(b+0>a+0)}'; then
      WORST_SW_CORNER="${ctag}"
    fi
    if awk -v a="${WORST_PFDQ_3S}" -v b="${c_pfdq_3s}" 'BEGIN{exit !(b+0>a+0)}'; then
      WORST_PFDQ_CORNER="${ctag}"
    fi
    if awk -v a="${WORST_PFDT_3S}" -v b="${c_pfdt_3s}" 'BEGIN{exit !(b+0>a+0)}'; then
      WORST_PFDT_CORNER="${ctag}"
    fi
    WORST_DCS_3S=$(awk -v a="${WORST_DCS_3S}" -v b="${c_dcs_3s}" 'BEGIN{print (a>b)?a:b}')
    WORST_DC_3S=$(awk -v a="${WORST_DC_3S}" -v b="${c_dc_3s}" 'BEGIN{print (a>b)?a:b}')
    WORST_SW_3S=$(awk -v a="${WORST_SW_3S}" -v b="${c_sw_3s}" 'BEGIN{print (a>b)?a:b}')
    WORST_PFDQ_3S=$(awk -v a="${WORST_PFDQ_3S}" -v b="${c_pfdq_3s}" 'BEGIN{print (a>b)?a:b}')
    WORST_PFDT_3S=$(awk -v a="${WORST_PFDT_3S}" -v b="${c_pfdt_3s}" 'BEGIN{print (a>b)?a:b}')
    WORST_DFF_3S=$(awk -v a="${WORST_DFF_3S}" -v b="${c_dff_3s}" 'BEGIN{print (a>b)?a:b}')
  done

  # The figures at the SHARED corner `ff_-40c_3.63v` -- the 3-point subset's own
  # binding corner, present in both this grid and the superseded record's.
  # #597's re-grading table uses it to separate the EXECUTION-HOST effect (same
  # corner, two hosts, different `agauss()` stream -- see the record's
  # cross-host bullet) from the CORNER-AXIS effect (this host, old binding
  # corner vs new one). Derived here rather than written into the record text,
  # so a re-run cannot leave a stale number behind; empty if the reference
  # corner is not in the grid, in which case the table below is suppressed.
  REF_CORNER="ff_-40c_3.63v"
  REF_DCS_3S=""; REF_SW_3S=""; REF_PFDQ_3S=""; REF_PFDT_3S=""
  # Terms 3 and 4 come out of the same sub-campaign and often, but not always,
  # bind at the same corner. Build the phrase here rather than in the record
  # heredoc: a conditional inside the heredoc has to emit its own backticks
  # through `printf`, where a backtick is not an escape and survives with the
  # backslash still attached.
  if [ "${WORST_PFDQ_CORNER}" = "${WORST_PFDT_CORNER}" ]; then
    WORST_QT_CORNER_PHRASE="\`${WORST_PFDQ_CORNER}\` (both terms)"
  else
    WORST_QT_CORNER_PHRASE="\`${WORST_PFDQ_CORNER}\` and \`${WORST_PFDT_CORNER}\` respectively"
  fi
  if printf '%s\n' "${CORNER_POINTS[@]}" | awk -v c="${REF_CORNER}" '
      { split($0, f, " "); if (f[1] "_" f[2] "c_" f[3] "v" == c) found = 1 }
      END { exit !found }'; then
    local r
    r=$(dc_worst signed "${REF_CORNER}" | simenv_stats_from_values)
    REF_DCS_3S=$(sig3 "$(echo "${r}" | awk '{print $1}')" "$(echo "${r}" | awk '{print $2}')")
    r=$(stats_corner "${OUT_SW}" 4 "${REF_CORNER}")
    REF_SW_3S=$(sig3 "$(echo "${r}" | awk '{print $1}')" "$(echo "${r}" | awk '{print $2}')")
    r=$(stats_corner "${OUT_PFD}" 3 "${REF_CORNER}")
    REF_PFDQ_3S=$(sig3 "$(echo "${r}" | awk '{print $1}')" "$(echo "${r}" | awk '{print $2}')")
    r=$(stats_corner "${OUT_PFD}" 7 "${REF_CORNER}")
    REF_PFDT_3S=$(sig3 "$(echo "${r}" | awk '{print $1}')" "$(echo "${r}" | awk '{print $2}')")
  fi

  # Term 1's standard error of the MEAN at its binding (worst) corner, and the
  # raw budget margin expressed in units of that SE -- issue #482's
  # "re-measure or re-state term 1's margin" ask. This is the standard error
  # of the SAMPLE MEAN (sd/sqrt(n)), a lower bound on the uncertainty in
  # WORST_DCS_3S itself (which also carries the 3-sigma multiplier's own
  # estimation error) -- reported as the honest, conservative side of that
  # uncertainty, not a claim of exact precision.
  WORST_DCS_SE=$(awk -v s="${WORST_DCS_SD}" -v n="${WORST_DCS_N}" 'BEGIN{printf "%.6g", (n>0)? s/sqrt(n) : 0}')
  WORST_DC_SE=$(awk -v s="${WORST_DC_SD}" -v n="${WORST_DC_N}" 'BEGIN{printf "%.6g", (n>0)? s/sqrt(n) : 0}')
  WORST_DC_MARGIN_SE=$(awk -v m="${WORST_DCS_3S}" -v se="${WORST_DCS_SE}" -v b="${TERM1_BUDGET_PCT}" 'BEGIN{printf "%.4g", (se>0)? (b-m)/se : 0}')
  # Budget utilisation under each reading, so the record states both.
  TERM1_UTIL_SIGNED=$(awk -v m="${WORST_DCS_3S}" -v b="${TERM1_BUDGET_PCT}" 'BEGIN{printf "%.3g", 100*m/b}')
  TERM1_UTIL_FOLDED=$(awk -v m="${WORST_DC_3S}" -v b="${TERM1_BUDGET_PCT}" 'BEGIN{printf "%.3g", 100*m/b}')

  # The verdict on term 1 is taken on the SIGNED statistic (issue #487) -- the
  # conservative reading, and the one design/README.md's budget column header
  # actually describes.
  V1=$(verdict "${WORST_DCS_3S}" "${TERM1_BUDGET_PCT}")
  V2=$(verdict "${WORST_SW_3S}" 3e-9)
  V2A=$(verdict "${WORST_SW_3S}" 2e-9)
  V3=$(verdict "${WORST_PFDQ_3S}" 20e-15)
  V4=$(verdict "${WORST_PFDT_3S}" 3e-9)

  # Combined static phase offset at the PFD input: the charge-pump-side term 4
  # statistic PLUS the divider-retiming flop's mismatch-driven clk->Q dispersion
  # (issue #482's "does the flop need its own budget line" question). Both are
  # phase offsets referred to the same node, so they are additive there, and
  # term 4's +-3 ns envelope is the budget they have to share. Checking the SUM
  # is what gives the flop contribution a verdict without inventing a second
  # budget line for a quantity that is not an up/down mismatch term. Worst
  # corners are taken independently (the two sub-campaigns' worst corners need
  # not coincide), which makes this a conservative bound, not a per-die figure.
  DFF_PLUS_T4=$(awk -v a="${WORST_PFDT_3S}" -v b="${WORST_DFF_SIG3}" 'BEGIN{printf "%.6g", a+b}')
  V4C=$(verdict "${DFF_PLUS_T4}" 3e-9)
  DFF_T4_SHARE=$(awk -v a="${WORST_DFF_SIG3}" -v t="${DFF_PLUS_T4}" 'BEGIN{printf "%.3g", (t>0)? 100*a/t : 0}')
}

# Pooled one-liners to stdout. Term 1 prints BOTH of its statistics, each
# under its own name, so the console output cannot be misread the way the
# record's table was (issue #487).
print_stats_summary() {
  echo "DC term1 SIGNED worst-of-3 (verdict statistic), pooled: mean=${DC_S_MEAN}% sd=${DC_S_SD}% |mean|+3sigma=${DC_S_3S}% (n=${DC_N})"
  echo "DC term1 FOLDED |worst mismatch|, pooled:               mean=${DC_MEAN}% sd=${DC_SD}% mean(|x|)+3*sd(|x|)=${DC_3S}% (n=${DC_N})"
  echo "SW term2a wskew, pooled: mean=${SW_MEAN}s sd=${SW_SD}s |mean|+3sigma=${SW_3S}s (n=$(( N_SW * NUM_CORNERS )))"
  echo "PFD term3 qnet0, pooled: mean=${PFD_Q_MEAN}C sd=${PFD_Q_SD}C |mean|+3sigma=${PFD_Q_3S}C (n=$(( N_PFD * NUM_CORNERS )))"
  echo "PFD term4 t_offset, pooled: mean=${PFD_T_MEAN}s sd=${PFD_T_SD}s |mean|+3sigma=${PFD_T_3S}s (n=$(( N_PFD * NUM_CORNERS )))"
  echo "DFF tcq_r, pooled: mean=${DFF_R_MEAN}s sd=${DFF_R_SD}s |mean|+3sigma=${DFF_R_3S}s (n=$(( N_DFF * NUM_CORNERS )))"
  echo "DFF tcq_f, pooled: mean=${DFF_F_MEAN}s sd=${DFF_F_SD}s |mean|+3sigma=${DFF_F_3S}s (n=$(( N_DFF * NUM_CORNERS )))"
}

# --restat <record-id | corners dir>: re-derive this campaign's statistics
# from an ALREADY-COMMITTED corners/<record-id>/ CSV set and print them. No
# ngspice, no xschem, no netlist export -- it only reads committed evidence,
# so it is the way to check what the current reduction code makes of a past
# campaign's raw samples without paying for (or fabricating) a new run. It
# deliberately does NOT mint or touch a record: sim/ is append-only, and a
# record is minted by a real run, not by re-reading one.
restat() {
  local dir="${1:-}"
  [ -n "${dir}" ] || { echo "usage: run.sh --restat <record-id | corners dir>" >&2; exit 2; }
  [ -d "${dir}" ] || dir="${EXP}/corners/${dir}"
  [ -d "${dir}" ] || { echo "ERROR: no such corners directory: ${1}" >&2; exit 1; }
  OUT_DC="${dir}/mc_cp_dc.csv"
  OUT_SW="${dir}/mc_cp_switch.csv"
  OUT_PFD="${dir}/mc_pfd_cp.csv"
  OUT_DFF="${dir}/mc_dff_ctq.csv"
  local f
  for f in "${OUT_DC}" "${OUT_SW}" "${OUT_PFD}" "${OUT_DFF}"; do
    [ -f "${f}" ] || { echo "ERROR: ${f} missing -- not a complete campaign directory" >&2; exit 1; }
  done
  # Schema + corner-grid guard. The pre-#146 nominal-only record
  # (`20260731-212614-640560e`) predates the corner column entirely -- its dc
  # CSV is `seed,vctrl_v,...`, not `corner,seed,vctrl_v,...`. Without this
  # check every per-corner filter below matches nothing, every statistic comes
  # out of an empty sample as 0, and the summary happily prints an all-PASS
  # verdict derived from no data at all. Refuse instead: a diagnostic that
  # fabricates a PASS is worse than one that does not run.
  # `head -1` closes its read end after the first line, which can SIGPIPE an
  # upstream `grep` still writing on a large file; under `set -o pipefail`
  # that 141 would masquerade as this check's own failure. Scope the waiver
  # to just this pipeline rather than disabling pipefail script-wide.
  local got_hdr
  got_hdr=$(set +o pipefail; grep -v '^#' "${OUT_DC}" | head -1)
  [ "${got_hdr}" = "${DC_HEADER}" ] || {
    echo "ERROR: ${OUT_DC} has header '${got_hdr}'," >&2
    echo "       expected '${DC_HEADER}' -- this is not a corner-combined campaign" >&2
    echo "       (records before #146 are single-corner and have no corner column)." >&2
    exit 1
  }
  # The corner grid `--restat` reduces over is the one the COMMITTED CSV holds,
  # not this script's current `CORNER_POINTS` (issue #597). #597 widened
  # CORNER_POINTS from 3 points to 21, and the two older corner-combined records
  # (`20260817-135712-0e9cfc9`, `20260923-095854-1655e11`) hold only the 3 --
  # so reducing them against the current array would report every one of the 18
  # absent corners as a missing-rows error and refuse to run at all. That would
  # break a reproduction path DR-018, sim/CHARACTERIZATION.md and
  # spec/lib/check-mismatch-charge-derivation.sh all name by record id. Reading
  # the grid out of the data instead makes `--restat` correct for ANY committed
  # campaign of this schema, past or future, which is what a
  # committed-evidence-only diagnostic should be. The tag parse below is the
  # inverse of `<bundle>_<temp>c_<supply>v`: bundle names contain no underscore
  # (sim/README.md's five MOS bundles), so field 1 is the bundle and the
  # temperature's leading `-` survives in field 2.
  local restat_points restat_line
  restat_points=$(simenv_datarows "${OUT_DC}" | awk -F, '{print $1}' | awk '!seen[$0]++' \
    | awk -F_ '{ t=$2; sub(/c$/, "", t); v=$3; sub(/v$/, "", v); print $1, t, v }')
  [ -n "${restat_points}" ] || {
    echo "ERROR: ${OUT_DC} holds no data rows -- nothing to reduce" >&2
    exit 1
  }
  CORNER_POINTS=()
  while IFS= read -r restat_line; do
    [ -n "${restat_line}" ] && CORNER_POINTS+=("${restat_line}")
  done <<<"${restat_points}"
  NUM_CORNERS=${#CORNER_POINTS[@]}
  echo "mc-cp-mismatch --restat: ${NUM_CORNERS} corner(s) read from the committed CSV"
  local point pc pt pv ctag
  for point in "${CORNER_POINTS[@]}"; do
    read -r pc pt pv <<<"${point}"
    ctag="${pc}_${pt}c_${pv}v"
    # Round-trip guard on the parse above: re-assembling the tag from the three
    # parsed fields has to match a tag actually present, or the split was wrong
    # (a bundle name with an underscore in it, say) and every per-corner filter
    # below would silently match nothing.
    # `grep -q` exits at the first match, closing its read end before
    # `simenv_datarows`'s pipeline finishes writing -- a SIGPIPE race that
    # under `set -o pipefail` can turn a real match into a false "no rows"
    # error (see the header-check comment above). `-c` must read to EOF to
    # produce an accurate count, so it can't race-quit; discard the count and
    # keep the same 0-vs-nonzero exit status `grep -q` gave us.
    simenv_datarows "${OUT_DC}" | grep -c "^${ctag}," >/dev/null || {
      echo "ERROR: ${OUT_DC} has no rows for corner '${ctag}' -- the corner tag" >&2
      echo "       parse above did not round-trip; the CSV's corner column does" >&2
      echo "       not follow '<bundle>_<temp>c_<supply>v'." >&2
      exit 1
    }
  done
  # Per-corner sample counts are whatever the committed CSVs hold, not this
  # script's current N_* defaults -- re-derive the sw/pfd/dff ones so the
  # pooled "(n=...)" annotations above are honest about the data being read.
  N_SW=$(( $(simenv_datarows "${OUT_SW}" | wc -l) / NUM_CORNERS ))
  N_PFD=$(( $(simenv_datarows "${OUT_PFD}" | wc -l) / NUM_CORNERS ))
  N_DFF=$(( $(simenv_datarows "${OUT_DFF}" | wc -l) / NUM_CORNERS ))

  compute_term_stats

  echo "mc-cp-mismatch --restat: re-derived from ${dir}"
  echo "  (committed samples only -- no simulation was run, no record was minted)"
  echo
  print_stats_summary
  echo
  echo "Per-corner breakdown:"
  echo "  | Corner | Term 1 signed |mean|+3sigma | Term 1 folded mean(|x|)+3sd(|x|) | Term 2/2a |mean|+3sigma | Term 3 |mean|+3sigma | Term 4 |mean|+3sigma | DFF clk->Q mismatch 3sigma (and mean delay) |"
  printf '%s' "${PERCORNER_ROWS}"
  echo
  echo "Worst corner (binding on the verdict):"
  echo "  term 1 SIGNED |mean|+3sigma = ${WORST_DCS_3S}% at ${WORST_DCS_CORNER} (mean ${WORST_DCS_MEAN}%, sd ${WORST_DCS_SD}%, n=${WORST_DCS_N}, SE ${WORST_DCS_SE}%)"
  echo "  term 1 FOLDED mean(|x|)+3*sd(|x|) = ${WORST_DC_3S}% at ${WORST_DC_CORNER} (sd ${WORST_DC_SD}%, n=${WORST_DC_N}, SE ${WORST_DC_SE}%)"
  echo "  term 1 verdict vs +-${TERM1_BUDGET_PCT}% (DR-018): ${V1}  [signed uses ${TERM1_UTIL_SIGNED}% of budget, folded ${TERM1_UTIL_FOLDED}%; margin ${WORST_DC_MARGIN_SE} SE of the mean]"
  echo "  term 2 ${WORST_SW_3S} s: ${V2} / term 2a: ${V2A} / term 3 ${WORST_PFDQ_3S} C: ${V3} / term 4 ${WORST_PFDT_3S} s: ${V4}"
  echo "  term 4 + DFF clk->Q 3sigma = ${DFF_PLUS_T4} s vs +-3 ns: ${V4C}"
}

# --------------------------------------------------------------------------
# Entry points
# --------------------------------------------------------------------------
# SIM_RESUME=1 (see the top-level driver below): each --one-* invocation
# writes its (sub-campaign, corner, seed[, dphi]) sample to a per-invocation
# output file that is unique across the whole grid (the outer xargs loop
# names it `${WORK}/<stage>_<corner-tag>_<seed>.csv`) -- so a non-empty
# existing file at that exact path IS the completed sample, and can be
# trusted without re-running ngspice. Guard is a no-op (falls through to the
# normal run_*) unless SIM_RESUME=1, so a plain invocation is unaffected.
if [ "${SIM_RESUME:-0}" = "1" ]; then
  case "${1:-}" in
    --one-dc|--one-sw|--one-pfd|--one-dff)
      if [ -n "${3:-}" ] && [ -s "${3}" ]; then
        echo "mc-cp-mismatch: SIM_RESUME=1 -- ${3} already present, skipping" >&2
        exit 0
      fi
      ;;
  esac
fi
case "${1:-}" in
  --one-dc) shift; run_dc "$@"; exit 0 ;;
  --one-sw) shift; run_sw "$@"; exit 0 ;;
  --one-pfd) shift; run_pfd "$@"; exit 0 ;;
  --one-dff) shift; run_dff "$@"; exit 0 ;;
  --restat) shift; restat "$@"; exit 0 ;;
esac

simenv_require_tools
mkdir -p "${WORK}"

echo "mc-cp-mismatch: exporting design/ via xschem ..."
"${REPO}/design/netlist.sh" --top pfd_cp "${WORK}" >/dev/null
[ -f "${NETLIST}" ] || { echo "ERROR: ${NETLIST} not produced" >&2; exit 1; }

[ -f "${DFF_NETLIST_SRC}" ] || {
  echo "ERROR: ${DFF_NETLIST_SRC} missing -- run design/netlist.sh" >&2
  exit 1
}
cat "${DFF_NETLIST_SRC}" "${DECK_DFF}" >"${DUT_DFF}"

if [ "${1:-}" = "--check" ]; then
  tmpdir=$(mktemp -d)
  trap 'rm -rf "${tmpdir}"' EXIT
  echo "mc-cp-mismatch --check: 2 samples per sub-campaign at nominal (${CORNER}/${TEMP}C/${VDD}V)"
  for s in 1 2; do run_dc "${s}" "${tmpdir}/dc.csv"; done
  for s in 1 2; do run_sw "${s}" "${tmpdir}/sw.csv"; done
  for s in 1 2; do run_pfd "${s}" "${tmpdir}/pfd.csv"; done
  for s in 1 2; do run_dff "${s}" "${tmpdir}/dff.csv"; done
  echo "${DC_HEADER}"; cat "${tmpdir}/dc.csv"
  echo "${SW_HEADER}"; cat "${tmpdir}/sw.csv"
  echo "${PFD_HEADER}"; cat "${tmpdir}/pfd.csv"
  echo "${DFF_HEADER}"; cat "${tmpdir}/dff.csv"
  exit 0
fi

echo "mc-cp-mismatch: N_DC=${N_DC} N_SW=${N_SW} N_PFD=${N_PFD} N_DFF=${N_DFF} PER CORNER x ${NUM_CORNERS} corners, $(simenv_jobs) parallel jobs"

# SIM_RESUME=1 skips the usual clean-slate wipe below AND (via each per-sample
# xargs entry's own existing-output check, see the `[ -s "$3" ]` guard added
# to the --one-* case below) re-running any (sub-campaign, corner, seed)
# combination whose output file already exists from a prior, interrupted
# invocation of this same script. Added during #146's own build: this shared
# host was observed to sometimes terminate a long-running background
# invocation of this script outright (killed process tree, not a script-level
# error) well before a full corner grid could complete -- with SIM_RESUME=1,
# re-running `./run.sh` after such a kill picks up only the missing samples
# rather than repeating (and re-paying the wall-clock cost of) everything
# already on disk. Off by default so a normal invocation is always a clean,
# from-scratch campaign, matching every other campaign in this repo.
if [ "${SIM_RESUME:-0}" != "1" ]; then
  rm -f "${WORK}"/dc_*.csv "${WORK}"/sw_*.csv "${WORK}"/pfd_*.csv "${WORK}"/dff_*.csv
else
  echo "mc-cp-mismatch: SIM_RESUME=1 -- keeping any already-completed per-sample CSVs from a prior run"
fi

for point in "${CORNER_POINTS[@]}"; do
  read -r pc pt pv <<<"${point}"
  ctag="${pc}_${pt}c_${pv}v"
  echo "mc-cp-mismatch: corner ${ctag} ..."
  seq 1 "${N_DC}" | xargs -P "$(simenv_jobs)" -I{} \
    env SIM_CORNER="${pc}" SIM_TEMP="${pt}" SIM_VDD="${pv}" \
    "${BASH:-/bin/bash}" -c "\"${HERE}/run.sh\" --one-dc {} \"${WORK}/dc_${ctag}_{}.csv\""
  seq 1 "${N_SW}" | xargs -P "$(simenv_jobs)" -I{} \
    env SIM_CORNER="${pc}" SIM_TEMP="${pt}" SIM_VDD="${pv}" \
    "${BASH:-/bin/bash}" -c "\"${HERE}/run.sh\" --one-sw {} \"${WORK}/sw_${ctag}_{}.csv\""
  seq 1 "${N_PFD}" | xargs -P "$(simenv_jobs)" -I{} \
    env SIM_CORNER="${pc}" SIM_TEMP="${pt}" SIM_VDD="${pv}" \
    "${BASH:-/bin/bash}" -c "\"${HERE}/run.sh\" --one-pfd {} \"${WORK}/pfd_${ctag}_{}.csv\""
  seq 1 "${N_DFF}" | xargs -P "$(simenv_jobs)" -I{} \
    env SIM_CORNER="${pc}" SIM_TEMP="${pt}" SIM_VDD="${pv}" \
    "${BASH:-/bin/bash}" -c "\"${HERE}/run.sh\" --one-dff {} \"${WORK}/dff_${ctag}_{}.csv\""
done

# The aggregate files below are named `<stage>_all.csv`, which MATCHES the
# `<stage>_*.csv` per-sample glob they are built from. On a from-scratch run
# that is harmless (the clean-slate wipe above removed them before the glob is
# expanded), but on a SIM_RESUME=1 re-run after a run that already COMPLETED,
# the previous aggregate is still on disk and would be concatenated into its
# own successor -- doubling every row and tripping the row-count assertions
# below with a count exactly 2x the expected one. Remove them explicitly so
# the resume path is correct regardless of how the previous run ended
# (issue #482, which re-minted a record from an already-complete work dir).
rm -f "${WORK}"/dc_all.csv "${WORK}"/sw_all.csv "${WORK}"/pfd_all.csv "${WORK}"/dff_all.csv
cat "${WORK}"/dc_*.csv | sort -t, -k1,1 -k2,2n >"${WORK}/dc_all.csv"
cat "${WORK}"/sw_*.csv | sort -t, -k1,1 -k2,2n >"${WORK}/sw_all.csv"
cat "${WORK}"/pfd_*.csv | sort -t, -k1,1 -k2,2n >"${WORK}/pfd_all.csv"
cat "${WORK}"/dff_*.csv | sort -t, -k1,1 -k2,2n >"${WORK}/dff_all.csv"

GOT_DC=$(wc -l <"${WORK}/dc_all.csv" | tr -d ' ')
GOT_SW=$(wc -l <"${WORK}/sw_all.csv" | tr -d ' ')
GOT_PFD=$(wc -l <"${WORK}/pfd_all.csv" | tr -d ' ')
GOT_DFF=$(wc -l <"${WORK}/dff_all.csv" | tr -d ' ')
[ "${GOT_DC}" -eq $(( N_DC * 3 * NUM_CORNERS )) ] || { echo "ERROR: expected $(( N_DC * 3 * NUM_CORNERS )) dc rows, got ${GOT_DC}" >&2; exit 1; }
[ "${GOT_SW}" -eq $(( N_SW * NUM_CORNERS )) ] || { echo "ERROR: expected $(( N_SW * NUM_CORNERS )) sw rows, got ${GOT_SW}" >&2; exit 1; }
[ "${GOT_PFD}" -eq $(( N_PFD * NUM_CORNERS )) ] || { echo "ERROR: expected $(( N_PFD * NUM_CORNERS )) pfd rows, got ${GOT_PFD}" >&2; exit 1; }
[ "${GOT_DFF}" -eq $(( N_DFF * NUM_CORNERS )) ] || { echo "ERROR: expected $(( N_DFF * NUM_CORNERS )) dff rows, got ${GOT_DFF}" >&2; exit 1; }

# --------------------------------------------------------------------------
# Mint the evidence record.
# --------------------------------------------------------------------------
RID=$(simenv_record_id)
SNAPDIR="${EXP}/netlist-snapshots"
CORNERSDIR="${EXP}/corners/${RID}"
RECORDSDIR="${EXP}/records"
mkdir -p "${SNAPDIR}" "${CORNERSDIR}" "${RECORDSDIR}"

cp "${NETLIST}" "${SNAPDIR}/${RID}-cppfd.spice"
cp "${DUT_DFF}" "${SNAPDIR}/${RID}-dff.spice"
SHA_CPPFD=$(simenv_sha256 "${SNAPDIR}/${RID}-cppfd.spice")
SHA_DFF=$(simenv_sha256 "${SNAPDIR}/${RID}-dff.spice")

# Archive every raw log -- the WORK subdir tag already carries corner+seed
# (and, for pfd, dphi), so the directory's own name is the archived filename.
for f in "${WORK}"/dc_*/ngspice.log "${WORK}"/sw_*/ngspice.log \
         "${WORK}"/pfd_*/ngspice.log "${WORK}"/dff_*/ngspice.log; do
  [ -f "${f}" ] || continue
  cp "${f}" "${CORNERSDIR}/$(basename "$(dirname "${f}")").log"
done

OUT_DC="${CORNERSDIR}/mc_cp_dc.csv"
OUT_SW="${CORNERSDIR}/mc_cp_switch.csv"
OUT_PFD="${CORNERSDIR}/mc_pfd_cp.csv"
OUT_DFF="${CORNERSDIR}/mc_dff_ctq.csv"
{
  simenv_provenance "mc-cp-mismatch (dc)" "${RID}" "design/cp.sch (xschem export)" \
    "${NUM_CORNERS} corners x N=${N_DC} mismatch samples/corner" "${SWITCHES_NOTE}"
  echo "${DC_HEADER}"; cat "${WORK}/dc_all.csv"
} >"${OUT_DC}"
{
  simenv_provenance "mc-cp-mismatch (switch)" "${RID}" "design/cp.sch (xschem export)" \
    "${NUM_CORNERS} corners, Vctrl=${VCTRL_MID}, N=${N_SW} mismatch samples/corner" "${SWITCHES_NOTE}"
  echo "${SW_HEADER}"; cat "${WORK}/sw_all.csv"
} >"${OUT_SW}"
{
  simenv_provenance "mc-cp-mismatch (pfd_cp)" "${RID}" "design/pfd_cp.sch (xschem export)" \
    "${NUM_CORNERS} corners, dphi={-1n,0,+1n}, N=${N_PFD} mismatch samples/corner" "${SWITCHES_NOTE}"
  echo "${PFD_HEADER}"; cat "${WORK}/pfd_all.csv"
} >"${OUT_PFD}"
{
  simenv_provenance "mc-cp-mismatch (dff clk->Q)" "${RID}" "design/dff_tg_3v3.sch (committed netlist)" \
    "${NUM_CORNERS} corners, N=${N_DFF} mismatch samples/corner x 2 (rise+fall)" "${SWITCHES_NOTE}"
  echo "${DFF_HEADER}"; cat "${WORK}/dff_all.csv"
} >"${OUT_DFF}"

# --------------------------------------------------------------------------
# Statistics + verdicts, from the just-written CSVs so the record text cannot
# drift from the data. Both helpers are defined near the top of this file so
# that `--restat` can reuse them against an already-committed campaign; see
# the "WHICH statistic" note there for term 1's signed-vs-folded pair
# (issue #487).
# --------------------------------------------------------------------------
compute_term_stats
print_stats_summary

# Term 1 exceedance note. design/README.md is explicit that if this campaign's
# statistics do not fit inside the stated budget, "the resolution is a decision
# record, not a quiet widening here" -- so a FAIL is reported as a FAIL, with
# the margin expressed in standard errors so a reader can tell an exceedance
# from sampling noise, and the required next step named. Emitted conditionally
# so a passing run's record is not cluttered with a hypothetical.
if [ "${V1}" = "FAIL" ]; then
  TERM1_NOTE="
  **Term 1 EXCEEDS its stated budget at the binding corner, and this record
  does not widen the budget to absorb it.** At \`N_DC=${N_DC}\`/corner the
  worst-corner term-1 statistic (signed \`|mean|+3sigma\`, issue #487) is
  ${WORST_DCS_3S}% against design/README.md's
  stated +-${TERM1_BUDGET_PCT}% (DR-018), i.e. the budget line sits $(awk -v x="${WORST_DC_MARGIN_SE}" 'BEGIN{printf "%.4g", (x<0?-x:x)}') standard errors of the mean BELOW the
  measured statistic (sd ${WORST_DCS_SD}%, n=${WORST_DCS_N}, SE ${WORST_DCS_SE}%)
  -- an exceedance, not a coin-flip. design/README.md's own rule for this case
  is explicit -- \"If #15's statistics or #10's spur analysis show these values
  do not buy the spur/jitter performance the ratified spec asks for, the
  resolution is a decision record superseding this budget -- not a quiet
  relaxation here\" -- so the budget column is left exactly as it stands and
  the resolution is deferred to a NEW decision record. DR-018 already spent
  the widening argument once (12% -> ${TERM1_BUDGET_PCT}%, derived from the
  ratified <= -55 dBc reference-spur line, which it leaves only ~1.6 dB of
  derived margin); a second widening needs a mechanism this campaign has not
  measured, not a repeat of that reasoning.
"
else
  TERM1_NOTE="
  **Term 1 fits, against the budget DR-018 derived rather than the +-12% that
  preceded it.** At \`N_DC=${N_DC}\`/corner the worst-corner term-1 statistic
  (signed \`|mean|+3sigma\`, issue #487) is ${WORST_DCS_3S}% against
  +-${TERM1_BUDGET_PCT}% (sd ${WORST_DCS_SD}%, n=${WORST_DCS_N},
  SE ${WORST_DCS_SE}%), i.e. the budget line sits
  ${WORST_DC_MARGIN_SE} standard errors of the mean ABOVE the measured
  statistic, and the measurement uses ${TERM1_UTIL_SIGNED}% of the budget.
  Readers comparing this against
  \`sim/mc-cp-mismatch/records/20260923-095854-1655e11.md\` -- which reports a
  FAIL on the same design -- should note that TWO things changed between the
  two records and NEITHER is the measurement: the BUDGET (#483/DR-018, +-12%
  -> +-${TERM1_BUDGET_PCT}%) and the STATISTIC this campaign reports term 1 as
  (#487, the folded \`mean(|x|)+3*sd(|x|)\` that record quotes -> the signed
  \`|mean|+3sigma\` above, which is LARGER on the same samples:
  ${WORST_DC_3S}% -> ${WORST_DCS_3S}% at this run's binding corner).
"
fi

RECORD="${RECORDSDIR}/${RID}.md"
cat >"${RECORD}" <<EOF
# Record ${RID}

- **Record ID**: ${RID}
- **Claim**: design/README.md's "Up/down mismatch budget" table (not yet a
  ratified spec line -- #1 is open) -- does RANDOM gf180mcu device mismatch,
  COMBINED WITH the repo's PVT process/temperature/supply corner grid (not
  just at nominal), on top of the SYSTEMATIC values \`cp-compliance\` and
  \`pfd-deadzone\` measure, fit inside the budget column that table states for
  terms 1, 2/2a, 3 and 4; and, separately, what is the divider-retiming flop's
  own clk->Q mismatch contribution to static phase offset, ALSO combined with
  the corner grid. Closes the T1/bronze checklist gap (#127, item 6:
  "Statistical claims / Monte Carlo evidence") the nominal-only record
  \`20260731-212614-640560e\` left open -- that record stands unmodified as
  historical evidence (append-only); this one adds the corner dimension on
  top of the same claim, it does not supersede or invalidate it.
  **This specific record widens the CORNER AXIS itself (issue #597)**, from the
  3-point diagonal subset \`sim/mc-cp-mismatch/records/20260817-135712-0e9cfc9.md\`
  (#146) chose and \`sim/mc-cp-mismatch/records/20260923-095854-1655e11.md\`
  (#482) inherited, to the ${NUM_CORNERS} points listed in the Corner-matrix
  field: nominal plus every vertex of the process x temperature x supply box,
  with the MOS-bundle axis swept in full. #482 raised the per-corner SAMPLE
  COUNTS and closed T1/bronze item 6's (#127) sub-criteria (a)-(c), but left
  the corner-combination sub-criterion (d) at three points, offering either a
  wider axis or a ratified justification for the subset; this record takes the
  wider axis, for the two reasons the Corner-matrix field's "What this grid
  replaced" note states -- both of them about what the 3-point set could not
  bound, not about its cost. \`fs\` and \`sf\`, absent from every prior record
  of this campaign, are measured here for the first time. It SUPERSEDES
  \`20260923-095854-1655e11\` for this claim (see Supersedes field) -- that
  record's bytes remain committed, unedited, as historical evidence, and its
  own per-corner numbers at the three shared points remain readable beside
  this record's.
  **Term 1 at the widened axis**: it measures ${WORST_DCS_3S}% at
  \`${WORST_DCS_CORNER}\` against the +-${TERM1_BUDGET_PCT}% budget in force
  (verdict **${V1}**), where the superseded record read 17.4798% at
  \`ff_-40c_3.63v\` on the same statistic and the same budget. The binding
  corner is the figure to compare between the two records, because the whole
  point of a widened axis is that the worst corner may not be a corner the
  narrower grid visited. Note also that BOTH term 1's budget (DR-018, #483:
  +-12% -> +-${TERM1_BUDGET_PCT}%) and the STATISTIC term 1 is reported as
  (#487: the signed \`|mean|+3sigma\`, replacing a folded
  \`mean(|x|)+3*sd(|x|)\` that earlier records mislabelled as
  \`|mean|+3sigma\`) changed before this record, so a difference against the
  OLDEST records is not necessarily a measurement difference. On THIS run's
  samples the two readings are ${WORST_DCS_3S}% (signed, the verdict) and
  ${WORST_DC_3S}% (folded, reported beside it).
- **Model-capability gate**: unchanged from the nominal-only record -- see
  \`sim/mc-cp-mismatch/records/20260731-212614-640560e.md\`'s "Model-capability
  gate" and "What did NOT work" notes for the full \`agauss()\`/parse-time-seed
  finding this campaign continues to rely on (\`nfet_03v3_dss\`/
  \`pfet_03v3_dss\` carry \`mis_vth = agauss(0, var_vth, 1)\` /
  \`mis_k = agauss(0, var_k, 1)\`, independent per instance, gated by
  \`sw_stat_mismatch\`, and \`.option rndseed=N\` -- not \`set rndseed=N\`
  inside \`.control\` -- is what makes the draws reproducible because they are
  evaluated once at netlist PARSE time). This record's own negative-control
  re-check (same seed -> same draws, \`sw_stat_mismatch=0\` -> seed-independent)
  was repeated at \`fs_125c_2.97v\` -- a MIXED MOS bundle, which no prior
  record of this campaign visited at all -- and confirmed the same behavior
  holds there, with the measured numbers quoted in full in the Methodology
  field's own negative-control bullet.
- **Netlist provenance**:
  - \`cp\`/\`pfd_cp\`: schematic (\`design/cp.sch\`, \`design/pfd_cp.sch\` and
    the cells below them) exported by \`design/netlist.sh --top pfd_cp\` ->
    \`sim/mc-cp-mismatch/netlist-snapshots/${RID}-cppfd.spice\`, SHA-256
    \`${SHA_CPPFD}\`
  - \`dff_tg_3v3\` (divider-retiming flop): committed export
    \`design/netlist/dff_tg_3v3.spice\`, frozen together with
    \`tb_mc_dff_ctq.sp\` into
    \`sim/mc-cp-mismatch/netlist-snapshots/${RID}-dff.spice\`, SHA-256
    \`${SHA_DFF}\`
  - Testbench decks contain stimulus, measurement and the
    \`sw_stat_mismatch\`/\`rndseed\` overrides only -- no hand-transcribed
    copy of the design. Unchanged from the nominal-only record; only
    \`run.sh\`'s corner-loop and per-invocation \`CORNER\`/\`TEMP\`/\`VDD\`
    plumbing changed for #146.
- **Environment provenance**:
$(simenv_env_block "$(simenv_xschem_version) (batch netlist export of
    \`design/\` via \`design/netlist.sh\`; the cp/pfd_cp DUT is a schematic
    export, dff_tg_3v3 is design/netlist/'s committed export)" \
  "\`design.ngspice\` included first; this campaign explicitly OVERRIDES its
    default \`sw_stat_mismatch = 0\` to \`sw_stat_mismatch = 1\` for every run
    (\`sw_stat_global\` stays at the design.ngspice default 0 -- mismatch
    only, global process variation off, exactly sim/README.md's worked
    distribution example), with \`.option rndseed\` set per sample (see the
    Statistical convention field)")
- **Corner matrix run**: ${NUM_CORNERS}-point subset of \`sim/README.md\`'s
  45-point default grid, combined with Monte Carlo sampling at each point.
  The points, listed exactly as \`run.sh\`'s \`CORNER_POINTS\` array holds them
  so this field cannot drift from what ran:

${CORNER_LIST_MD}
  The set is \`typical/27C/3.30V\` (nominal) plus **all ${NUM_VERTICES}
  vertices of the process x temperature x supply box** -- each of the five MOS
  bundles \`sim/README.md\` defines (\`typical\`, \`ss\`, \`ff\`, \`fs\`,
  \`sf\`) crossed with both temperature extremes (-40 C, 125 C) and both
  supply extremes (2.97 V, 3.63 V). The MOS-bundle axis is swept in FULL.
  **Axes not swept**: the $(( 45 - NUM_CORNERS )) remaining default-grid points
  are exactly those interior on the temperature axis (27 C) and/or the supply
  axis (3.30 V) at a non-nominal bundle -- every one of them lies between two
  visited vertices at the same MOS bundle on each continuous axis. Passive
  corner sections (\`res_*\`, \`mimcap_*\`, \`moscap_*\`) N/A -- the DUTs are
  \`nfet_03v3\`/\`pfet_03v3\` only, same as every prior record of this
  campaign.
  **Justification** (sim/README.md's "Default corner matrix" rule requires
  one for any subset): the omitted points are interior to the measured box on
  the two continuous axes, and the per-corner breakdown table below is the
  evidence a reader grades that against -- for an omitted point to bind, its
  dispersion would have to exceed BOTH bracketing vertices at the same MOS
  bundle, i.e. behave non-monotonically in temperature or supply between two
  measured values. This record states that bracketing and shows the table; it
  does not assert monotonicity as a physical law.
  **What this grid replaced, and why (issue #597)**: records
  \`sim/mc-cp-mismatch/records/20260817-135712-0e9cfc9.md\` (#146) and
  \`sim/mc-cp-mismatch/records/20260923-095854-1655e11.md\` (#482) ran THREE
  points -- \`typical/27C/3.30V\`, \`ss/125C/2.97V\`, \`ff/-40C/3.63V\` -- and
  #482 explicitly left the corner axis as the open half of T1/bronze item 6's
  corner-combination sub-criterion (#127), offering either a wider axis or a
  ratified justification for the 3-point set. The wider axis is what ran here,
  because the 3-point set's bounding argument does not hold on this repo's own
  evidence, in two independent ways:
  1. **\`fs\`/\`sf\` were absent and are structurally the worst case for this
     measurement.** Term 1 is an UP/DN match between a PMOS source and an NMOS
     sink; \`ss\`/\`ff\` skew both flavours the same way and largely preserve
     that ratio, while \`fs\`/\`sf\` skew them oppositely and attack it
     directly. This repo has already measured that asymmetry binding at a
     mixed bundle elsewhere: \`sim/cp-compliance\`'s switching bench binds at
     \`fs\`/125C/3.63V (3.68 fC worst-corner \`wskew\`, the figure
     \`spec/pll.md\`'s reference-spur derivation consumes), and
     \`sim/lock-window-sizing\`'s two window edges bind at \`fs\` and \`ss\`.
  2. **The temp/supply axis was sampled on one diagonal only.** (125C, 2.97V)
     and (-40C, 3.63V) were visited; the anti-diagonal (-40C, 2.97V) and
     (125C, 3.63V) were not. Mirror mismatch dispersion scales with
     \`gm/I * sigma(Vth)\`, largest at least overdrive -- cold AND low supply
     -- which is precisely the vertex the diagonal omitted.
  **Why ${NUM_CORNERS} and not 45**: the cost analysis in \`run.sh\`'s header
  comment still rules out the full grid; what it no longer rules out is the
  vertex set. #146's own build discovered, mid-build, that this host's ngspice
  is compiled with OpenMP-parallel BSIM evaluation, so \`simenv_jobs\`
  process-level parallelism was compounding with per-process thread
  parallelism -- fixed via \`export OMP_NUM_THREADS=1\`, measured ~44x
  wall-clock improvement on one isolated \`sw\` invocation (7m48s -> 10.7s for
  essentially unchanged CPU-seconds). That fix arrived too late to be priced
  into #146's own grid decision, and it is what moved the affordable corner
  count by roughly an order of magnitude. Re-measured for THIS grid on this
  host (isolated invocations, fix applied, host load ~12 of 18 cores): dc
  1.2 s, sw 30 s, pfd 57 s per seed (three sequential transients), dff 2.3 s.
  The shared-host variance #146 documented (the same isolated \`sw\`
  invocation measuring 10.7 s, 1m40s and 57 min on different occasions, purely
  from other tenants' load) is unchanged and is still why 45 points is not
  attempted: a campaign whose per-invocation cost can swing ~300x cannot
  budget a fixed sample count against a fixed wall-clock target.
- **Methodology / criteria / limitations**:
  - **dc** (term 1): \`alter\`+\`op\` at Vctrl = 0.9/1.65/2.4 V, \`N_DC=${N_DC}\`
    single-instance invocations PER CORNER (\`$(( N_DC * NUM_CORNERS ))\` total),
    one \`.option rndseed\` per sample. The per-sample reduction is the
    WORST-MAGNITUDE of the 3 Vctrl points, matching \`cp-compliance\`'s own
    "worst point in window" convention for term 1.
  - **Which statistic term 1 is reported as (issue #487)**: the selection
    above is by MAGNITUDE, but the statistic formed from the selected samples
    is now the SIGNED \`|mean| + 3*sigma\`, and that is what the verdict is
    taken on. Earlier records of this campaign folded the samples to \`|x|\`
    FIRST and reported \`mean(|x|) + 3*sd(|x|)\` while calling it
    \`|mean|+3sigma\` -- two different statistics, the folded one being the
    LESS conservative (folding merges the distribution's two tails, shrinking
    both the mean and the sd; on record \`20260923-095854-1655e11\`'s committed
    300 samples the binding corner reads 13.2172% folded against 17.4798%
    signed, and 13.2172% is not a clean quantile either -- roughly the 98.5th
    percentile, where a 3-sigma tail sits at 99.87th). DR-018 §Context and
    §Decision priced the +-${TERM1_BUDGET_PCT}% budget against BOTH readings
    and pre-authorised reporting the signed form "without a further record",
    so this is a reporting correction, not a budget change -- and it moves the
    number UP. Both are reported here: signed ${WORST_DCS_3S}% (verdict) and
    folded ${WORST_DC_3S}% at their respective binding corners.
  - **Terms 2/2a, 3 and 4 were checked for the same defect and do not have
    it**: their samples are reduced by \`stats\`/\`stats_corner\`, which take
    the CSV column as it stands (no absolute value anywhere in the path) and
    form \`|mean| + 3*sigma\` on the signed series -- so the label those
    columns carry has always matched the statistic underneath it. They also
    have no worst-of-N-points selection step, which is what made term 1's
    reduction reach for a magnitude in the first place. The divider-retiming
    flop's figure is \`3*sigma\` with no \`|mean|\` term (see its own bullet
    below) and is likewise unfolded.
  - **Term 1's margin, re-measured at raised n (issue #482)**: the prior
    record (n=20/corner) passed term 1 at 11.7211% against the +-12% budget
    in force at that time, at its binding corner (\`ff\`/-40C/3.63V) -- a 2.3%
    relative margin, the thinnest of the four budget terms, and one that
    record's own text called out as too close to call from n=20 alone. At
    \`N_DC=${N_DC}\`/corner, the binding corner for the verdict statistic is
    \`${WORST_DCS_CORNER}\`, whose signed worst-point samples have mean
    ${WORST_DCS_MEAN}% and sample standard deviation ${WORST_DCS_SD}%
    (n=${WORST_DCS_N}) -> standard error of the mean ${WORST_DCS_SE}%. The
    budget headroom (${TERM1_BUDGET_PCT}% minus the signed
    \`|mean|+3sigma\` figure below) is ${WORST_DC_MARGIN_SE} standard errors
    of the mean at this sample size -- a NEGATIVE value means the measured
    statistic has crossed the budget, by that many standard errors, rather
    than sitting inside it. This is the sample MEAN's standard
    error, a lower bound on the full statistic's uncertainty (the
    \`|mean|+3sigma\` figure also carries the 3-sigma multiplier's own
    estimation error on top) -- reported so the verdict's margin can be
    weighed against sampling noise explicitly rather than read as an exact
    percentage. The folded companion figure's own binding corner is
    \`${WORST_DC_CORNER}\` (sd ${WORST_DC_SD}%, n=${WORST_DC_N}, SE
    ${WORST_DC_SE}%); note the mean/sd pair quoted here is the SIGNED one,
    which is the distribution the 3-sigma tail is actually taken from.
  - **sw** (terms 2/2a): transient switching bench at Vctrl = 1.65 V ONLY
    (mid-window, same scope decision as the nominal-only record -- see that
    record's Methodology field for the post-#24 flatness finding this
    inherits), \`N_SW=${N_SW}\` single-instance invocations PER CORNER
    (\`$(( N_SW * NUM_CORNERS ))\` total).
  - **pfd** (terms 3/4 + PFD-path mismatch): full \`pfd_cp\` hierarchy at
    Vctrl = 1.65 V, dphi in {-1 ns, 0, +1 ns}, \`N_PFD=${N_PFD}\` samples PER
    CORNER (\`$(( N_PFD * NUM_CORNERS ))\` total), 3 invocations each sharing
    one \`.option rndseed\`. \`qnet0\` = term 3; \`kd_wide = (q(+1n) - q(-1n))
    / 2ns\`; \`t_offset = qnet0 / kd_wide\` = term 4. PFD-path mismatch is
    folded into this same measurement, not separable -- see the nominal-only
    record's Methodology field for the full explanation, unchanged here.
  - **dff** (divider-retiming flop): single clean 0->1 / 1->0 capture per
    invocation, \`N_DFF=${N_DFF}\` invocations PER CORNER x 2 directions
    (\`$(( N_DFF * NUM_CORNERS * 2 ))\` total samples). Same one-for-one
    phase-offset conversion as the nominal-only record. **The reported
    statistic changed in this record (issue #482)**: the flop's contribution is
    now quoted as \`3sigma\` (mismatch dispersion ONLY, no \`|mean|\` term),
    with the mean clk->Q delay reported beside it rather than folded into it.
    The earlier \`|mean|+3sigma\` form is the correct worst-case magnitude for
    terms 1-4, whose means are errors centred near zero, but for a
    propagation delay it reports mostly the delay itself -- a quantity
    \`sim/divider-ratio-dff\` already sweeps over the full 45-point grid and
    checks against the divider chain's retiming margin. See the Result field
    for the numbers and the resulting budget-line decision. The pooled
    all-corner \`sigma\` for this sub-campaign is deliberately NOT used as the
    flop's dispersion figure for the same reason: pooling across corners mixes
    the systematic corner-to-corner delay spread (${DFF_MEAN_MIN} s to
    ${DFF_MEAN_MAX} s across this record's ${NUM_CORNERS} corners, a span the
    widened axis makes larger still than the 3-point subset's) into what is
    supposed to be a within-corner mismatch sigma, inflating it by roughly an
    order of magnitude.
  - **Per-corner sample sizes are unchanged from
    \`sim/mc-cp-mismatch/records/20260923-095854-1655e11.md\` (issue #482's
    raise) and are still short of the nominal-only record's n=40**
    (n=${N_SW}/corner for sw, n=${N_PFD}/corner for pfd, n=${N_DC}/corner for
    dc, n=${N_DFF}/corner for dff -- see this file's header comment for the
    timing measurement that motivated that raise and the reasoning for not
    going further). #597 spent its wall-clock budget on the CORNER axis rather
    than on n, which is the tradeoff \`run.sh\`'s header comment names
    explicitly: at these per-corner counts the breakdown table below answers
    "is any corner's dispersion qualitatively worse than nominal's" -- which is
    what a corner-combination criterion asks -- but not "what is corner X's
    sigma to two significant figures". The pooled (all-corners) statistic
    reported above the table now rests on ${NUM_CORNERS} corners' samples
    rather than 3, so it is a tighter combined-distribution estimate than any
    prior record's, but it is NOT the verdict statistic, for the
    corner-mixing reason the dff bullet above gives. A future pass wanting
    tighter PER-corner sigmas would need to either shrink the corner set again
    or accept a larger total wall clock; this record does not attempt that
    tradeoff.
  - **Negative-control re-check at a non-nominal corner, repeated at a NEWLY
    ADDED MIXED BUNDLE (issue #597)**: run manually (not part of \`run.sh\`, to
    avoid adding wall clock to every future run). The superseded record checked
    \`ff_-40c_3.63v\`; this record repeats the same two checks at
    \`fs_125c_2.97v\` -- a bundle no prior record of this campaign visited at
    all -- so item 6's deterministic-negative-control sub-criterion is met at
    the widened axis and not only at the axis it replaced. Two
    \`tb_mc_cp_dc.sp\` invocations at \`fs\`/125C/2.97V with the SAME
    \`rndseed=7\` and \`sw_stat_mismatch=1\` produced byte-identical
    \`iup\`/\`idn\` at all three Vctrl points (\`iup=5.37859E-06
    idn=5.35313E-06\` / \`5.37306E-06\`, \`5.37675E-06\` / \`5.35868E-06\`,
    \`5.39239E-06\` for LO/MID/HI); and \`sw_stat_mismatch=0\` with two
    DIFFERENT seeds (11, 12) at that same corner produced identical output to
    each other (\`iup=5.33363E-06 idn=5.41078E-06\` / \`5.32799E-06\`,
    \`5.43735E-06\` / \`5.31351E-06\`, \`5.45498E-06\`), i.e. seed-independent,
    confirming the switch and not the seed gates the draw. The
    parse-time-seeding finding therefore holds on the mixed bundles too, not
    just on the same-direction \`ss\`/\`ff\` ones. (Those mismatch-off figures
    are also the fs systematic baseline: -2.02% at mid-Vctrl, which is the
    \`|mean|\` this corner's dispersion sits on top of.)
  - **THE SAME SEED DOES NOT PRODUCE THE SAME DRAW ON A DIFFERENT HOST, and
    this record is the first in this campaign to be able to show it (issue
    #597).** Every prior record of this campaign states that
    \`.option rndseed=N\` makes the draws reproducible, and that is true --
    but only within one build on one machine. The superseded record
    \`20260923-095854-1655e11\` was taken with ngspice-46 on Linux/x86_64; this
    one is ngspice-46 on the host named in the Environment provenance field
    above. Both cover \`ff\`/-40C/3.63V at seeds 1..100, from the same deck and
    the same committed CSV schema, so the two can be compared row for row --
    and seed 1 is a DIFFERENT DRAW, not a slightly different numerical answer
    to the same one:

    | corner=\`ff_-40c_3.63v\`, seed 1 | Vctrl 0.9 V | 1.65 V | 2.4 V |
    |---|---|---|---|
    | \`20260923-095854-1655e11\` (Linux/x86_64) | +6.4859% | +5.9503% | +5.2664% |
    | this record | +3.7754% | +3.1553% | +2.3918% |

    Those differ by ~2.7 percentage points on a quantity whose whole
    per-corner sd is ~4%, which is a different sample from the same
    distribution rather than solver noise -- \`agauss()\` is drawing off a
    different random stream. Read together with **DR-028**, which measured
    this repo's same-version CROSS-HOST reproducibility floor on a
    DETERMINISTIC quantity (period jitter, +3.71% and +9.31% relative), the
    distinction matters: for a deterministic measurement a cross-host re-run
    is a reproducibility CHECK, and for a Monte Carlo one it is an independent
    REPLICATE. So a per-seed comparison across hosts is meaningless and a
    DISTRIBUTION-level comparison is the only one available -- which is what
    the re-grading bullet below does, and why it separates the two effects
    instead of attributing the whole difference to the widened axis. The
    campaign's reproducibility claim should be read as "same host, same build,
    same seed -> same draw", which is what the negative control above actually
    verifies. Nothing here weakens \`--restat\`: it re-reduces COMMITTED
    samples and is exactly reproducible anywhere.
  - **Re-grading the terms whose binding corner or figure moved, with the host
    effect separated from the corner effect (issue #597).** Two things changed
    between \`20260923-095854-1655e11\` and this record -- the corner axis
    (3 -> ${NUM_CORNERS} points) and the execution host (see the bullet above)
    -- so a bare difference between the two records attributes nothing. Both
    records cover \`ff\`/-40C/3.63V, the old grid's binding corner, so that
    shared corner isolates the host effect and the rest is the axis:

    | Term | old record @ \`${REF_CORNER}\` | this record @ \`${REF_CORNER}\` | host effect | this record's WORST corner | axis effect |
    |---|---|---|---|---|---|
    | 1, signed \`\|mean\|+3sigma\` | 17.4798% | ${REF_DCS_3S}% | $(awk -v a="${REF_DCS_3S}" 'BEGIN{printf "%+.4f", a-17.4798}') pt | **${WORST_DCS_3S}%** at \`${WORST_DCS_CORNER}\` | $(awk -v a="${WORST_DCS_3S}" -v r="${REF_DCS_3S}" 'BEGIN{printf "%+.4f", a-r}') pt |
    | 2/2a, \`\|mean\|+3sigma\` | 2.75395e-10 s | ${REF_SW_3S} s | $(awk -v a="${REF_SW_3S}" 'BEGIN{printf "%+.1f", (a-2.75395e-10)*1e12}') ps | **${WORST_SW_3S} s** at \`${WORST_SW_CORNER}\` | $(awk -v a="${WORST_SW_3S}" -v r="${REF_SW_3S}" 'BEGIN{printf "%+.1f", (a-r)*1e12}') ps |
    | 3, \`\|mean\|+3sigma\` | 4.25246e-15 C | ${REF_PFDQ_3S} C | $(awk -v a="${REF_PFDQ_3S}" 'BEGIN{printf "%+.3f", (a-4.25246e-15)*1e15}') fC | **${WORST_PFDQ_3S} C** at \`${WORST_PFDQ_CORNER}\` | $(awk -v a="${WORST_PFDQ_3S}" -v r="${REF_PFDQ_3S}" 'BEGIN{printf "%+.3f", (a-r)*1e15}') fC |
    | 4, \`\|mean\|+3sigma\` | 8.64436e-10 s | ${REF_PFDT_3S} s | $(awk -v a="${REF_PFDT_3S}" 'BEGIN{printf "%+.1f", (a-8.64436e-10)*1e12}') ps | **${WORST_PFDT_3S} s** at \`${WORST_PFDT_CORNER}\` | $(awk -v a="${WORST_PFDT_3S}" -v r="${REF_PFDT_3S}" 'BEGIN{printf "%+.1f", (a-r)*1e12}') ps |

    The "old record" column is that record's own committed figures, quoted
    verbatim; every other number is derived from this record's CSVs at record
    time. The "host effect" column is the same corner on two hosts and the
    "axis effect" column is this host's old binding corner against its new
    one, so the two columns add to the total difference by construction.

    Three findings follow, and all four terms still PASS:

    1. **A NEWLY ADDED MIXED BUNDLE now binds term 1.** The worst corner is
       \`${WORST_DCS_CORNER}\` -- an \`sf\` point, a bundle no prior record of
       this campaign visited. That is the prediction \`run.sh\`'s header comment
       makes about why \`fs\`/\`sf\` could not be assumed bounded by \`ss\`/\`ff\`,
       confirmed rather than asserted. The margin it moves the figure by is
       small -- the axis-effect column above -- which is the honest size of the
       finding: the 3-point subset was not wildly wrong about term 1's
       magnitude, it was unable to say so.
    2. **The binding corner for terms 3 and 4 moved to ${WORST_QT_CORNER_PHRASE}, also new, and by a
       margin that is NOT small.** Term 3 rises from ${REF_PFDQ_3S} C at the old
       binding corner to ${WORST_PFDQ_3S} C, i.e. most of its increase over the
       superseded record is the corner axis, not the host.
       **This matters beyond this record**, because term 3's statistical
       residual is an input to \`spec/pll.md\`'s reference-spur derivation:
       DR-018 priced that stack with term 3 at 4.25246 fC, and the worst
       corner of the widened grid reads higher. That does not change the
       verdict here (term 3's own budget is +-20 fC and it uses
       $(awk -v x="${WORST_PFDQ_3S}" 'BEGIN{printf "%.1f", 100*x/20e-15}')% of
       it) and this record does NOT re-derive the spur stack or touch
       DR-018 -- per CLAUDE.md a spec change goes through \`spec/\` with a
       decision record, and re-pricing a ratified derivation is not something a
       campaign runner does as a side effect. What this record owes is the
       measurement and the flag, and both are here.
    3. **Term 2/2a's worst corner also moved to a new point** and roughly
       doubled over the superseded record (${WORST_SW_3S} s at
       \`${WORST_SW_CORNER}\`, against 2.75395e-10 s). It still uses
       $(awk -v x="${WORST_SW_3S}" 'BEGIN{printf "%.1f", 100*x/3e-9}')% of its
       +-3 ns budget, so this is headroom consumed rather than a verdict
       changed -- but it is the clearest single illustration of why an interior
       diagonal is not a bound: nothing in the 3-point subset hinted at it.
  - **Closed-loop reference-spur check: NOT performed, honest gap, not
    fabricated.** Unchanged from the nominal-only record -- #12's
    lock-time/output-range bench has since landed on \`main\`, but wiring a
    closed-loop conversion of these open-loop terms into a spur estimate is a
    separate, already-tracked gap (#127's checklist), not this issue's (#146)
    scope, which is specifically the MC-combined-with-corners extension and
    the VCO band-select mirror characterization. The open-loop terms above
    (1-4) are fully substantiated, now combined with the corner grid; the
    closed-loop conversion remains deferred.
  - Bias generation is out of scope and idealized, exactly as the
    nominal-only record and \`cp-compliance\`/\`pfd-deadzone\`/\`devchar-cp\`.
- **Statistical convention**: \`sw_stat_global = 0\`, \`sw_stat_mismatch = 1\`
  (mismatch-only, global process variation off). Per-corner sample counts:
  \`N_DC=${N_DC}\`, \`N_SW=${N_SW}\`, \`N_PFD=${N_PFD}\`, \`N_DFF=${N_DFF}\`
  (x2 for dff's rise/fall), each x ${NUM_CORNERS} corners. Distribution
  reported at mean +/- sample standard deviation (N-1 denominator) and at
  \`|mean| + 3*sigma\` on the SIGNED samples -- for every term, with no
  absolute value taken before the statistic is formed (issue #487) -- both
  pooled (all corners combined) and per corner. Term 1 additionally reports
  the folded \`mean(|x|) + 3*sd(|x|)\` that earlier records of this campaign
  used as their (mislabelled) headline figure, so the two conventions can be
  compared directly on the same draws; the flop's figure is \`3*sigma\` with
  no \`|mean|\` term, for the reason its own bullet gives.
  Seeds: sequential integers \`1..N\` PER (sub-campaign, corner) -- i.e. the
  same seed value 1 is reused at each of the ${NUM_CORNERS} corners, which is fine because
  a corner change (different \`.lib\` sections, different \`.temp\`/\`vsup\`)
  changes the circuit the same seed's draw is applied to; every seed's raw
  log is committed under \`corners/${RID}/\`, named by its full
  (sub-campaign, corner, seed[, dphi]) tag.
- **Result -- worst corner (binding on the budget verdict)**:

  | # | Term | Statistical, worst-corner \|mean\|+3sigma (signed samples) | Budget (design/README.md) | Verdict |
  |---|---|---|---|---|
  | 1 | DC UP/DN mismatch, worst of 0.9/1.65/2.4 V | ${WORST_DCS_3S}% (folded \`mean(\|x\|)+3*sd(\|x\|)\`: ${WORST_DC_3S}%) | +-${TERM1_BUDGET_PCT}% (DR-018) | **${V1}** |
  | 2 | Switching-time skew, whole window (assessed at mid-window) | ${WORST_SW_3S} s | +-3 ns | **${V2}** |
  | 2a | Switching-time skew, mid-window (Vctrl=1.65 V) | ${WORST_SW_3S} s | +-2 ns | **${V2A}** |
  | 3 | Residual net charge at zero phase error | ${WORST_PFDQ_3S} C | +-20 fC | **${V3}** |
  | 4 | Static phase offset, q_zero / Kd | ${WORST_PFDT_3S} s | +-3 ns | **${V4}** |
${TERM1_NOTE}
  **Divider-retiming flop clk->Q mismatch, worst corner -- now checked against
  something (issue #482).** The flop's mismatch-driven clk->Q DISPERSION is
  \`3sigma\` = ${WORST_DFF_SIG3} s at \`${WORST_DFF_SIG3_CORNER}\`
  (n=${WORST_DFF_SIG3_N}), on a mean clk->Q delay of ${WORST_DFF_SIG3_MEAN} s at
  that corner. Added to term 4 at the PFD input -- the same node, so the two
  are additive there -- the combined worst-case static phase offset is
  ${DFF_PLUS_T4} s against term 4's stated +-3 ns envelope: **${V4C}**. The
  flop contributes ${DFF_T4_SHARE}% of that sum.

  **This is why the flop does NOT get its own budget-table line**, which is
  the question issue #482 asked. Two reasons, both measured rather than
  asserted:

  1. It is not an up/down mismatch term and not a charge-pump/PFD block term.
     design/README.md's table already applies exactly this exclusion to the
     bias generator ("it is a separate block ... the budget must be re-derived
     rather than silently absorbed").
  2. The number that made it look budget-sized was the wrong statistic. Prior
     records quoted the flop's \`|mean|+3sigma\` (${WORST_DFF_3S} s at its
     worst corner) alongside terms 1-4's, but those terms' means are ERRORS
     centred near zero while the flop's mean is a nominal PROPAGATION DELAY.
     At this campaign's worst corner the mean is
     $(awk -v m="${WORST_DFF_SIG3_MEAN}" -v t="${WORST_DFF_3S}" 'BEGIN{printf "%.3g", (t>0)? 100*m/t : 0}')% of that figure -- i.e. it was reporting a
     systematic delay, not a mismatch contribution, and that systematic delay
     is already swept over the full 45-point grid by
     \`sim/divider-ratio-dff\` (record \`20260801-125114-3f883e3\`, worst-case
     \`tcq_r\` 3.70952e-10 s at \`ss\`/125C/2.97V -- which this campaign's own
     worst-corner mean reproduces) and already checked there, against the
     divider chain's retiming setup/hold margin. A budget line here would
     double-count it.

  What was genuinely unchecked was the DISPERSION, and the combined-offset
  check above is now its verdict.

- **Result -- per-corner breakdown**:

  | Corner | Term 1 \|mean\|+3sigma (signed; verdict) | Term 1 \`mean(\|x\|)+3*sd(\|x\|)\` (folded) | Term 2/2a \|mean\|+3sigma | Term 3 \|mean\|+3sigma | Term 4 \|mean\|+3sigma | DFF clk->Q mismatch 3sigma (and mean delay) |
  |---|---|---|---|---|---|---|
${PERCORNER_ROWS}
- **Result -- pooled (all ${NUM_CORNERS} corners combined; reported for
  completeness, NOT the verdict statistic -- pooling across corners mixes the
  systematic corner-to-corner spread into a within-corner mismatch sigma, which
  is the same reason the dff bullet gives for not pooling there)**:

  | # | Term | Pooled mean / sd / \|mean\|+3sigma (n) |
  |---|---|---|
  | 1 | DC UP/DN mismatch, worst of 0.9/1.65/2.4 V (signed) | ${DC_S_MEAN}% / ${DC_S_SD}% / ${DC_S_3S}% (n=${DC_N}) |
  | 1' | -- the same samples folded to \|x\| first (\`mean(\|x\|)+3*sd(\|x\|)\`, the pre-#487 convention) | ${DC_MEAN}% / ${DC_SD}% / ${DC_3S}% (n=${DC_N}) |
  | 2/2a | Switching-time skew, mid-window | ${SW_MEAN} s / ${SW_SD} s / ${SW_3S} s (n=$(( N_SW * NUM_CORNERS ))) |
  | 3 | Residual net charge at zero phase error | ${PFD_Q_MEAN} C / ${PFD_Q_SD} C / ${PFD_Q_3S} C (n=$(( N_PFD * NUM_CORNERS ))) |
  | 4 | Static phase offset, q_zero / Kd | ${PFD_T_MEAN} s / ${PFD_T_SD} s / ${PFD_T_3S} s (n=$(( N_PFD * NUM_CORNERS ))) |

  **Systematic vs. statistical, kept distinct** (unchanged convention from
  the nominal-only record): design/README.md's "Systematic (measured, all 45
  PVT corners)" column (terms 1-4) is the corner-swept MEAN (\`sw_stat_mismatch
  = 0\`). This record's numbers are the ADDITIONAL statistical dispersion
  \`sw_stat_mismatch = 1\` adds on top, now itself corner-swept over the
  ${NUM_CORNERS}-point vertex set named in the Corner-matrix field. They are
  not interchangeable and this record does not add them together.
- **Links**:
  - Testbenches: \`sim/mc-cp-mismatch/testbench/tb_mc_cp_dc.sp\`,
    \`tb_mc_cp_switch.sp\`, \`tb_mc_pfd_cp.sp\`, \`tb_mc_dff_ctq.sp\`,
    \`run.sh\`
  - Design: \`design/cp.sch\`, \`design/cp_dumpbuf.sch\`, \`design/pfd_cp.sch\`,
    \`design/pfd.sch\`, \`design/dff_tg_3v3.sch\`
  - Netlist snapshots:
    \`sim/mc-cp-mismatch/netlist-snapshots/${RID}-cppfd.spice\`,
    \`sim/mc-cp-mismatch/netlist-snapshots/${RID}-dff.spice\`
  - Raw logs: \`sim/mc-cp-mismatch/corners/${RID}/\`
  - Extracted metrics: \`sim/mc-cp-mismatch/corners/${RID}/mc_cp_dc.csv\`,
    \`mc_cp_switch.csv\`, \`mc_pfd_cp.csv\`, \`mc_dff_ctq.csv\`
  - Prior record (nominal-only MC, not superseded, historical evidence):
    \`sim/mc-cp-mismatch/records/20260731-212614-640560e.md\`
  - Prior corner-combined records, at the 3-point diagonal subset this record's
    axis replaces (both keep their bytes; the later one is superseded by this
    record for this claim): \`sim/mc-cp-mismatch/records/20260817-135712-0e9cfc9.md\`
    (#146), \`sim/mc-cp-mismatch/records/20260923-095854-1655e11.md\` (#482)
  - Reduced-corner-grid precedent this record's axis exceeds:
    \`sim/lock-detector/testbench/run.sh\` (\`WINDOW_CORNERS\`, 5 points)
  - Mixed-bundle binding precedent cited in the Corner-matrix field:
    \`sim/cp-compliance/records/20260802-061841-c24ee3a.md\` (worst-corner
    \`wskew\` at \`fs\`/125C/3.63V), \`sim/lock-window-sizing/\` (window edges
    binding at \`fs\` and \`ss\`)
- **Timestamp / author**: $(date -u +%Y-%m-%dT%H:%M:%SZ), agent-builder (issue #597)
$(simenv_supersedes_field "${SIM_SUPERSEDES:-}")
EOF

echo "mc-cp-mismatch: wrote ${RECORD}"
echo "mc-cp-mismatch: wrote ${OUT_DC}, ${OUT_SW}, ${OUT_PFD}, ${OUT_DFF}"
echo "mc-cp-mismatch: wrote ${CORNERSDIR}/ ($(( (N_DC + N_SW + N_PFD * 3 + N_DFF) * NUM_CORNERS )) corner logs)"
