#!/usr/bin/env bash
# gf180-pll :: output-range :: closed-loop output-band coverage campaign (#12)
#
# DUT: `pll_top` -- the whole PLL from design/pll_top.sch, prepended to
# tb_output_range.sp by sim/lib/pll_top_dut.sh (#52); the same DUT
# sim/lock-time, sim/pll-top-smoke and sim/supply-sensitivity build. See
# sim/lock-time's run.sh header for why sim/lib/simenv.sh is used here rather
# than sim/harness's tb.json.
#
# What this measures: for each of the two ratified output-band EDGE
# frequencies (10 MHz and 200 MHz -- draft 10-200 MHz target band, pending
# spec ratification #1), does the closed loop actually lock there, and with
# how much control-voltage headroom to the 0.9-2.7 V usable window. This
# complements (cites, does not re-derive) #8's open-loop
# sim/vco-tuning-range characterization: the (band, N, f_ref) design point
# for each edge, and the vctrl_ic seed used to keep the simulated transient
# tractable, are both taken directly from vco-tuning-range's own measured
# kvco_by_point.csv (see seed_for_corner below and this campaign's record).
#
# Usage:
#   ./run.sh                 # full 45-point PVT grid x both band edges, 90 runs
#   ./run.sh --plan          # print the joblist (incl. per-corner seeds) and exit
#                             #   -- no simulation, for reviewing/costing a grid
#   ./run.sh --check         # one short debug run, nominal corner, to stdout
#   ./run.sh --one <corner> <temp_c> <vdd> <edge> <fout> <b2> <b1> <b0> <n> \
#                 <vctrl_ic> <outcsv> [seed_pos]
#                             # single targeted point (used by the lo-edge
#                             #   anomaly-investigation record; bypasses the grid).
#                             #   A <vctrl_ic> that differs from what
#                             #   seed_for_corner would compute for this exact
#                             #   point is appended to the work-dir tag (#170),
#                             #   so re-running the same point at a DIFFERENT
#                             #   seed (a seed-control run) cannot collide with
#                             #   -- and silently reuse the log of -- another
#                             #   invocation's run. A grid row's own seed IS
#                             #   seed_for_corner's output, so this is a no-op
#                             #   for the full grid: tags, and therefore an
#                             #   existing work/ tree's reusability, are
#                             #   unchanged.
#   SIM_JOBS=4 ./run.sh      # parallelism (default: sequential -- see below)
#   SIM_WINCAP=2.5e-7 ./run.sh --one ...
#                             # shorten the transient window for a CONTROLLED
#                             #   sub-experiment only (appears in the work-dir
#                             #   tag; see run_one). Same discipline as
#                             #   SIM_TMAX: not a knob for making a grid finish.
#   SIM_RUNCAP=2400 ./run.sh [--one ...]
#                             # wall-clock budget in SECONDS for each point's
#                             #   ngspice invocation (#168). Unlike SIM_WINCAP
#                             #   this does NOT shorten the requested transient
#                             #   (tstop is unchanged, so a row that finishes
#                             #   under the cap is the SAME measurement as an
#                             #   uncapped one) -- it only bounds how long
#                             #   run.sh will wait for ngspice before killing
#                             #   it and its whole process group. Off by
#                             #   default (unset -> unbounded, the behaviour
#                             #   every existing record was taken under).
#                             #   Appears in the work-dir tag like SIM_WINCAP,
#                             #   and a cap that fires is reported with its own
#                             #   status `CAPPED` -- never `ERROR` -- so a
#                             #   budget termination can never be read as the
#                             #   simulator's own verdict (the distinction
#                             #   #168 exists to make; see run_with_cap).
#                             #   Exists for exactly one point in this
#                             #   campaign's grid that does not converge in
#                             #   tractable time -- see #168 -- not a knob for
#                             #   silently truncating any other row.
#
# NOTE ON HOST CONTENTION: exactly as for sim/lock-time, this campaign's real
# cost is dominated by wall-clock contention rather than raw CPU-seconds (the
# same corner/window has measured an order of magnitude apart on a contended
# vs. idle host -- see sim/lock-time/records/20260801-073931-eec269e.md).
# Check `uptime` before committing to the full 90-run invocation, and use
# `--plan` first if you want the joblist without paying for it.
#
# NOTE ON COST, POST-#65: this bench was the WORSE of the two closed-loop
# internal-timestep-bound violators. Its print step is 1/(50*f_out), so before
# #65 the `lo` (10 MHz) edge ran with a 2 ns internal ceiling -- 20x over the
# PFD's 100 ps bound, with 91% of its internal steps longer than the PFD's
# entire set pulse (sim/lock-time/records/20260801-101734-5eb00db.md). The
# ceiling is now passed explicitly (sim/lib/simenv.sh :: SIMENV_CLOSED_LOOP_TMAX),
# which raises `lo`'s internal step count roughly 20x; `hi` (200 MHz) is
# unchanged, because 1/(50*200 MHz) happened to equal 100 ps exactly. Budget
# the grid accordingly, and do NOT reach for SIM_TMAX to claw the time back --
# a grid minted at a coarser ceiling is not evidence about this loop.
#
# NOTE ON COST, POST-#159: this campaign's deck previously carried BOTH a
# top-level `.tran` card and a `.control ... run` block, which makes ngspice
# batch mode execute the transient TWICE -- the mechanism behind the
# "ngspice re-entered its own analysis path a second time" observation this
# campaign's own records report. #159's deck issues it once, from the control
# block, so historical per-run CPU-second figures are roughly twice what the
# same row costs now.
#
# DUT MIGRATION (#159): until #159 this campaign built its DUT with
# sim/lib/assemble_closed_loop.sh, which concatenates the five committed block
# exports and leaves the loop's top-level wiring to the testbench's own
# instance list. It now builds it with sim/lib/pll_top_dut.sh, from the
# committed export of design/pll_top.sch. Every record already in
# sim/output-range/records/ was taken against the older DUT and names it in
# its own Netlist provenance field; those records are append-only and are
# neither edited nor reinterpreted by this change. The first record taken
# against `pll_top` is 20260819-160843-4e32f91 (#164) -- the full 90-run grid,
# which supersedes the single-corner pilot 20260731-223426-640560e. The
# equivalent re-take for sim/lock-time (#163) is still open, and #159's own
# remaining scope (deleting sim/lib/assemble_closed_loop.sh) waits on it.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP="$(cd "${HERE}/.." && pwd)"
REPO="$(cd "${EXP}/../.." && pwd)"
# shellcheck source=../../lib/simenv.sh
. "${HERE}/../../lib/simenv.sh"
# shellcheck source=../../lib/pll_top_dut.sh
. "${HERE}/../../lib/pll_top_dut.sh"

FRAGMENT="${HERE}/tb_output_range.sp"
WORK="${EXP}/work"
# The deck actually handed to ngspice: the committed pll_top export with this
# campaign's stimulus fragment appended, so the frozen netlist snapshot a
# record cites is self-contained.
DECK="${WORK}/dut_output_range.sp"

# Read-only design-input evidence this campaign cites (#8) -- never written
# to, never re-derived here.
KVCO_CSV="${REPO}/sim/vco-tuning-range/corners/20260731-175947-0a12e6c/kvco_by_point.csv"

# Icp trim named by CODE (#159): the bits come from sim/lib/pll_top_dut.sh's
# cloop_trim_params, which owns the encoding for every campaign on this DUT.
# Code 2 = (CPB1 CPB0) 1 0 -- the same nominal setting this campaign has
# always run. The VCO band is per-edge (see EDGES below) and goes through
# cloop_band_params the same way.
ICP_CODE=2
IUNIT=8u

# PFD DN-branch integration guard floor (#69) -- see
# sim/lock-time/testbench/run.sh's identical constant and run_one for the full
# rationale.  Same floor as sim/pll-top-smoke's check 7, so no two campaigns
# can disagree about what "the DN branch asserted" means.
ACC_DN_FRAC=3e-4

# --------------------------------------------------------------------------
# Canonical per-row CSV schema. Defined ONCE and reused by every writer
# (`--check`'s scratch CSV and the campaign's RESULT_CSV) so the header and
# run_one's row emission cannot drift apart. Field indices are load-bearing --
# the awk tallies and the markdown table generator below both address columns
# positionally:
#
#   $1  corner        $6  n              $11 k_cells
#   $2  temp_c        $7  fref_hz        $12 seed_v      (per-corner vctrl_ic, #65)
#   $3  vdd_v         $8  status         $13 seed_pos    (in/below/above, #65)
#   $4  edge          $9  t_lock_s       $14 dn_lvl_v    (PFD DN-branch guard, #69)
#   $5  fout_hz       $10 vctrl_final_v  $15 dn_guard    (PFD DN-branch guard, #69)
#
# Columns 12-13 (the seeding pair, this campaign's stimulus) and 14-15 (the
# DN-branch guard pair, a per-row check on the internal-timestep ceiling) were
# added independently and are both kept: stimulus columns first, then the
# guard's measurement + verdict last.
# --------------------------------------------------------------------------
CSV_HEADER="corner,temp_c,vdd_v,edge,fout_hz,n,fref_hz,status,t_lock_s,vctrl_final_v,k_cells,seed_v,seed_pos,dn_lvl_v,dn_guard"

# --------------------------------------------------------------------------
# Two edges of the draft 10-200 MHz v1 output band. Band code and N are read
# off sim/vco-tuning-range's own measured kvco_by_point.csv. N is chosen as a
# power of two purely for a simple divider code; f_ref lands well inside the
# ratified 1-25 MHz v1 reference range either way.
#   low  edge: band 1 (B2 B1 B0=0 0 1), N=8  -> f_ref=1.25 MHz
#   high edge: band 7 (B2 B1 B0=1 1 1), N=32 -> f_ref=6.25 MHz
# The vctrl_ic seed is NOT fixed here -- it is interpolated PER CORNER by
# seed_for_corner below (see that function's comment for why the original
# single fixed seed does not survive the grid extension).
# --------------------------------------------------------------------------
EDGES=(
  "lo 10e6 0 0 1 8  1"
  "hi 200e6 1 1 1 32 7"
)

# --------------------------------------------------------------------------
# Grid.  #65 item 4 extends this campaign from the original deliberately-
# reduced single-corner pilot (`sim/output-range/records/20260731-223426-640560e.md`,
# 2 runs at typical/27C/3.30V) to the FULL 45-point PVT grid at both band
# edges -- the same grid loop sim/lock-time/testbench/run.sh already carries,
# applied to this script.
# --------------------------------------------------------------------------
BUNDLES=("${SIMENV_MOS_CORNERS[@]}")
TEMPS=("${SIMENV_TEMPS[@]}")
VDDS=("${SIMENV_VDDS[@]}")

# Single-point debug corner, used only by --check below.
CORNER="typical"; TEMP=27; VDD=3.30

# --------------------------------------------------------------------------
# seed_for_corner <bundle> <temp_c> <vdd> <band> <f_target> -> "<vctrl_v> <pos>"
#
# The vctrl_ic seed this bench applies through its released clamp, read off
# #8's own kvco_by_point.csv AT THE CORNER BEING RUN and linearly interpolated
# between the two bracketing Vctrl rows -- exactly the rule the pilot record
# (20260731-223426-640560e) applied by hand at its single corner, now applied
# programmatically at all 45. Verified against that record before being
# trusted: it reproduces the pilot's own hand-computed seeds, 1.679 V vs. its
# stated 1.68 V (lo) and 1.321 V vs. its stated 1.32 V (hi).
#
# Why per-corner rather than the pilot's two fixed constants: the VCO's f(Vctrl)
# curve moves a long way over PVT -- band 1 reaches 10 MHz anywhere from 1.17 V
# (ss/125C/2.97V) to 2.06 V (sf/-40C/3.63V). Carrying the nominal-corner seed
# across the grid would start most corners with a large control-voltage error
# and then give the loop the SAME short transient window to correct it in, so a
# FAIL row would confound "the loop cannot reach this edge here" with "the seed
# was for a different corner". Seeding per corner keeps the initial error small
# and corner-independent, so what varies across the grid is the loop, not the
# stimulus.
#
# <pos> is `in` when the target frequency falls inside the tabulated
# 0.9-2.7 V Vctrl sweep at that corner, `below`/`above` when it falls off
# the bottom/top end -- in which case the seed is clamped to the corresponding
# rail and the row is reported as OUT-OF-WINDOW rather than silently seeded at
# a Vctrl the open-loop table says cannot produce that frequency. That is a
# real design-input result (this band code cannot reach this edge at this
# corner), not a simulation failure, and the record says so.
# --------------------------------------------------------------------------
seed_for_corner() {
  awk -F, -v bundle="$1" -v temp="$2" -v vdd="$3" -v band="$4" -v ftarget="$5" '
    # n MUST be initialized: an uninitialized awk scalar used as a subscript
    # is the empty STRING, so the first matched row would land in v[""] and
    # leave v[0]/f[0] unset -- silently interpolating the lowest bracket
    # against a phantom (0 V, 0 Hz) point.
    BEGIN { n = 0 }
    NR == 1 { next }
    $1 == bundle && $2 + 0 == temp + 0 && $3 + 0 == vdd + 0 && $4 + 0 == band + 0 {
      v[n] = $5 + 0; f[n] = $6 + 0; n++
    }
    END {
      if (n < 2) { print "ERROR nodata"; exit }
      if (ftarget <= f[0])   { printf "%.4g below\n", v[0];   exit }
      if (ftarget >= f[n-1]) { printf "%.4g above\n", v[n-1]; exit }
      for (i = 0; i < n - 1; i++) {
        if (ftarget >= f[i] && ftarget <= f[i+1]) {
          printf "%.4g in\n", v[i] + (v[i+1] - v[i]) * (ftarget - f[i]) / (f[i+1] - f[i])
          exit
        }
      }
      print "ERROR nobracket"
    }
  ' "${KVCO_CSV}"
}

# row_tag <corner> <temp> <vdd> <edge> [<vctrl_ic> <band> <fout>]
#
# The work-directory tag for one row, i.e. that row's RUN IDENTITY. Defined
# once and used by BOTH run_one (which writes the run dir) and the
# record-minting loop (which archives it), so the two can never disagree about
# where a row's log lives -- before #168 the mint loop rebuilt the tag inline
# without the SIM_WINCAP suffix, so a short-window grid archived nothing.
#
# The three trailing arguments are the SEED IDENTITY of the row, and are
# optional only as a group: pass all three or none. They carry #172's `vctrl_ic`
# disambiguation (#170), which lives INSIDE this function for the same
# single-definition reason the rest of the tag does -- computing the seed suffix
# in run_one and appending it to this function's return value would both skip
# the `.`->`p` substitution below (yielding `_ic1.4540001` where #172 produced
# `_ic1p4540001`) and leave the mint loop building a tag without it, which is
# exactly the run-dir/archive divergence #168 hoisted this function to prevent.
#
# The internal-timestep ceiling is part of the run's identity -- see
# sim/lock-time/testbench/run.sh's run_one for why it goes in the tag.
#
# SIM_WINCAP (#159) shortens the transient window, and exists for the single
# legitimate use sim/lock-time documents for its own copy: a CONTROLLED
# sub-experiment where the same corner is run twice in one environment with a
# single variable changed, or a wiring/regression check of the deck itself at
# the compliant ceiling. It is NOT a knob for making a grid finish -- a row
# minted at a truncated window is not the same measurement as its neighbours.
#
# SIM_RUNCAP (#168) is orthogonal to it and the distinction is load-bearing:
# SIM_WINCAP changes WHAT IS MEASURED (a shorter tstop, so the row is not
# comparable to its neighbours even when it completes); SIM_RUNCAP does not
# touch tstop at all, so a row that finishes under the cap IS comparable --
# the cap only bounds how long run.sh waits before giving up. See run_with_cap.
#
# Both are appended to the tag when set and omitted entirely when unset, so
# default tags are byte-identical to the pre-#168 ones and no capped or
# short-window log can ever be silently reused for a full-window record.
#
# CALLERS MUST WRITE `tag=$(row_tag ...) || exit 1`. This function validates
# the two environment knobs and its own seed arguments, and it runs inside a
# command substitution, so its `exit 1` ends only that subshell -- without the
# caller's `|| exit 1` a rejected SIM_WINCAP/SIM_RUNCAP would print its error
# and then carry on with an empty tag.
row_tag() {
  local corner="$1" temp="$2" vdd="$3" edge="$4"
  local vctrl_ic="${5:-}" band="${6:-}" fout="${7:-}"
  local wintag="" runcaptag="" seedtag=""
  # `vctrl_ic` seed disambiguation (#170, landed as #172): a full-grid
  # invocation always passes run_one the SAME seed seed_for_corner would
  # compute for this exact (corner, temp, vdd, band, fout) row, but the `--one`
  # entry point takes vctrl_ic as an explicit argument precisely so a single
  # point can be re-run with a DIFFERENT seed (e.g. a seed-control run at the
  # same PVT/edge). Without this check two such `--one` invocations land in the
  # SAME work-dir tag, and run_one's `-nt "${DECK}"` reuse guard then hands the
  # second invocation the first invocation's log under the second invocation's
  # (unrelated) seed -- silently, with no warning.
  #
  # Recomputing the canonical seed here and comparing is a no-op for every
  # full-grid row (the recomputed value is byte-identical to what was passed
  # in, since both come from the same seed_for_corner call), so grid tags are
  # UNCHANGED and a resumed grid's work/ tree stays fully reusable -- this is
  # the "include the seed only when it differs" alternative from #170's Scope,
  # chosen specifically to avoid invalidating an in-progress 90-run grid. Only
  # a `--one` invocation given a seed that does NOT match the canonical one
  # (including one seed_for_corner cannot itself resolve, e.g. an off-grid
  # corner) gets a distinct tag.
  #
  # All three or none: seed_for_corner needs the band and target frequency as
  # well as the PVT point, so accepting vctrl_ic alone could only ever silently
  # DROP the suffix -- which is the failure mode this whole function exists to
  # rule out. Rejected loudly instead.
  if [ -n "${vctrl_ic}" ] || [ -n "${band}" ] || [ -n "${fout}" ]; then
    if [ -z "${vctrl_ic}" ] || [ -z "${band}" ] || [ -z "${fout}" ]; then
      echo "ERROR: row_tag's seed arguments are all-or-nothing: got vctrl_ic='${vctrl_ic}' band='${band}' fout='${fout}'" >&2
      exit 1
    fi
    local canon_seed canon_vic
    canon_seed=$(seed_for_corner "${corner}" "${temp}" "${vdd}" "${band}" "${fout}")
    canon_vic="${canon_seed%% *}"
    if [ "${canon_vic}" = "ERROR" ] || \
       [ "$(awk -v a="${vctrl_ic}" -v b="${canon_vic}" 'BEGIN{print (a+0==b+0)?1:0}')" != "1" ]; then
      seedtag="_ic${vctrl_ic}"
    fi
  fi
  if [ -n "${SIM_WINCAP:-}" ]; then
    # SECONDS, as a plain decimal or scientific-notation number -- NOT a SPICE
    # engineering suffix; awk parses "250n" as a string and would silently
    # yield a 250 SECOND transient. Rejected loudly instead.
    case "${SIM_WINCAP}" in
      *[!0-9.eE+-]*|"")
        echo "ERROR: SIM_WINCAP='${SIM_WINCAP}' must be seconds as a plain number (e.g. 2.5e-7), not a SPICE suffix" >&2
        exit 1 ;;
    esac
    wintag="_w${SIM_WINCAP}"
  fi
  if [ -n "${SIM_RUNCAP:-}" ]; then
    # Whole seconds only: run_with_cap counts them with shell integer
    # arithmetic, and "0" would mean "kill before ngspice starts", which is
    # never what anyone means.
    case "${SIM_RUNCAP}" in
      *[!0-9]*|""|0)
        echo "ERROR: SIM_RUNCAP='${SIM_RUNCAP}' must be a wall-clock budget in whole seconds > 0 (e.g. 2400)" >&2
        exit 1 ;;
    esac
    runcaptag="_cap${SIM_RUNCAP}"
  fi
  local tag="or_${corner}_${temp}c_${vdd}v_${edge}_tmax${SIMENV_CLOSED_LOOP_TMAX}${wintag}${runcaptag}${seedtag}"
  # AFTER the seed suffix is appended, not before: `_ic1.4540001` has to become
  # `_ic1p4540001` like every other dot in the tag (#172's own behaviour).
  echo "${tag//./p}"
}

# run_with_cap <seconds> <command...>
#
# Runs <command...> (here, always simenv_run_deck) with a wall-clock ceiling
# (#168, SIM_RUNCAP): if it is still running after <seconds>, kills the WHOLE
# process group -- not just the immediate child -- so a still-spinning
# ngspice descendant cannot outlive the cap. `set -m` is scoped to this
# function only (restored immediately after backgrounding), so the
# backgrounded job gets its own process group via ordinary job-control
# semantics without changing signal handling anywhere else in this script.
#
# Deliberately not built on GNU/BSD `timeout`: macOS ships no `timeout(1)` in
# the base system, and this campaign's own records were all taken on a Darwin
# host, so depending on coreutils here would make the cap silently unavailable
# on exactly the machine the capped row was measured on.
#
# The budget is enforced against a DEADLINE taken from the clock, not by
# counting `sleep 1` iterations. Measured, not theoretical: the counting form
# overshot a 2400 s budget by 397 s (16.5%) on the contended host this
# campaign's own runner header warns about, because each iteration costs
# `sleep 1` PLUS the loop's own syscalls and the scheduler's latency, and that
# error is proportional to how loaded the machine is. A budget whose real
# value depends on host load is not a reproducible experimental parameter, and
# reproducibility is the entire reason this mechanism exists rather than a
# manual kill.
#
# Returns 124 (matching GNU timeout's own convention, so a caller can tell a
# capped run from any other nonzero exit) if the cap fired, otherwise the
# wrapped command's own exit status.
run_with_cap() {
  local cap="$1"; shift
  local pid rc=0 deadline
  deadline=$(( $(date +%s) + cap ))
  set -m
  "$@" &
  pid=$!
  set +m
  while kill -0 "${pid}" 2>/dev/null; do
    if [ "$(date +%s)" -ge "${deadline}" ]; then
      kill -TERM -- "-${pid}" 2>/dev/null || kill -TERM "${pid}" 2>/dev/null
      sleep 2
      kill -KILL -- "-${pid}" 2>/dev/null || kill -KILL "${pid}" 2>/dev/null
      wait "${pid}" 2>/dev/null || true
      return 124
    fi
    sleep 1
  done
  wait "${pid}" 2>/dev/null || rc=$?
  return "${rc}"
}

# run_one <corner> <temp> <vdd> <edge> <fout> <b2> <b1> <b0> <n> <vctrl_ic> \
#         <outcsv> [seed_pos]
#
# `seed_pos` is optional and defaults to `in`, so the single-point `--one`
# invocations the anomaly-investigation records used keep working unchanged.
run_one() {
  local corner="$1" temp="$2" vdd="$3" edge="$4" fout="$5" b2="$6" b1="$7" b0="$8" n="$9"
  shift 9
  local vctrl_ic="$1" outcsv="$2" seed_pos="${3:-in}"
  # Idempotent and cheap (only rewrites the file when the bytes change), so a
  # bare `--one` invocation -- the single-point form the anomaly
  # investigations use -- assembles its own deck rather than depending on a
  # prior full-grid invocation having left one behind.
  cloop_assemble "${FRAGMENT}" "${DECK}"
  local divparams; divparams=$(cloop_divider_params "${n}")
  local k; k=$(simenv_k_from_divparams "${divparams}")
  # The `--one` interface still takes the three band bits individually (that
  # is the form the existing anomaly-investigation records document); the
  # 0..7 code they spell is reassembled here so the actual .param bits still
  # come from the shared encoder rather than from this script.
  local band=$(( b2 * 4 + b1 * 2 + b0 ))
  local fref; fref=$(awk -v f="${fout}" -v n="${n}" 'BEGIN{printf "%.8g", f/n}')
  local tag
  tag=$(row_tag "${corner}" "${temp}" "${vdd}" "${edge}" \
                "${vctrl_ic}" "${band}" "${fout}") || exit 1

  local tstop tstep t_force
  # Seeded near the expected lock point, so acquiring the residual error is
  # fast -- see the campaign header and this record's Methodology field for
  # why (the same compute-cost constraint sim/lock-time documents).
  #
  # `tstep` is the PRINT step only. Before #65 this deck's transient omitted
  # the 4th (tmax) argument, so ngspice defaulted the INTERNAL timestep ceiling to
  # this print step -- and because it is derived from f_out, the 10 MHz `lo`
  # edge ran at a 2 ns internal ceiling, ~20x coarser than the PFD's set pulse
  # can tolerate. The ceiling is now passed independently as
  # SIMENV_CLOSED_LOOP_TMAX; note the resulting cost is strongly edge-dependent
  # here (the `lo` edge's internal step count rises ~18x, `hi`'s is unchanged
  # -- 200 MHz already computed to exactly 100 ps).
  tstop=$(awk -v fr="${fref}" -v cap="${SIM_WINCAP:-2e-6}" 'BEGIN{t=20/fr; if (t>cap) t=cap; printf "%.6g", t}')
  tstep=$(awk -v fo="${fout}" 'BEGIN{printf "%.6g", 1/(50*fo)}')
  t_force=$(awk -v fr="${fref}" 'BEGIN{printf "%.6g", 0.02/fr}')

  local params=(
    "vsup=${vdd}" "fref=${fref}" "iunit=${IUNIT}"
    "vctrl_ic=${vctrl_ic}" "t_force=${t_force}"
    "tstep=${tstep}" "tstop=${tstop}" "tmax=${SIMENV_CLOSED_LOOP_TMAX}"
    "lockthresh=0.5*vsup"
  )
  # Word splitting of each helper's `name=value ...` line is exactly what is
  # wanted here: one array element per .param.
  # shellcheck disable=SC2206
  params+=( ${divparams} )
  # shellcheck disable=SC2207
  params+=( $(cloop_band_params "${band}") )
  # shellcheck disable=SC2207
  params+=( $(cloop_trim_params "${ICP_CODE}") )

  local log="${WORK}/${tag}/ngspice.log"
  # Idempotent re-run, and correct fatal-vs-benign classification -- see
  # sim/lock-time/testbench/run.sh's run_one for the full rationale (a
  # ".measure ... failed!" line is a legitimate "did not lock in this
  # window" outcome, not a broken deck, and must not be conflated with a
  # real environment/simulation failure, nor cost a re-simulation on retry).
  # "Completed" is judged by whether the transient itself produced the
  # vctrl_final reading, NOT by ngspice's own "Total analysis time" banner:
  # on at least one corner this DUT's ngspice run printed a complete,
  # internally-consistent set of measurements and THEN re-entered its own
  # analysis/gmin-stepping path a second time before exiting (observed, not
  # fully root-caused -- see this record's Methodology); gating completion
  # on the final banner alone would discard that real, already-computed
  # result.
  #
  # The `-nt "${DECK}"` guard is new with #159: the deck is now a GENERATED
  # artifact and the work-dir tag does not encode its contents, so without it
  # a log produced by a previous version of the stimulus fragment could be
  # silently reused under a new record's ID. cloop_assemble leaves an
  # unchanged deck's mtime alone, so a resumed grid still reuses everything it
  # legitimately can.
  if [ -f "${log}" ] && [ "${log}" -nt "${DECK}" ] && grep -q "^vctrl_final" "${log}"; then
    : # reuse the existing log below
  else
    local libs; libs=$(simenv_bundle_libs "${corner}")
    local capfired=0
    if [ -n "${SIM_RUNCAP:-}" ]; then
      local rc=0
      run_with_cap "${SIM_RUNCAP}" simenv_run_deck "${DECK}" "${WORK}" "${tag}" "${libs}" "${temp}" "${params[@]}" >/dev/null || rc=$?
      # 124 is run_with_cap's own "the budget fired" code (GNU timeout's
      # convention). Any other nonzero is simenv_run_deck's normal
      # failure path and is classified below exactly as it was before #168.
      if [ "${rc}" -eq 124 ]; then
        capfired=1
        # A capped kill leaves whatever ngspice had already logged -- for the
        # point #168 exists for, just the DC/"Initial Transient Solution"
        # print, because a stalled transient produces no periodic progress
        # output of its own. Append an explicit marker so the ARCHIVED log
        # (sim/lib/simenv.sh's simenv_archive_log copies this file verbatim)
        # states in its own text that the cap fired -- distinguishing this
        # from BOTH an ngspice-reported convergence abort (the sf/lo ERROR
        # rows, which name a node and a timestep) and the ad-hoc SIGTERM the
        # #164 record had to disclose for this row.
        if [ -f "${log}" ]; then
          printf '\n==== SIM_RUNCAP=%ss: run.sh killed ngspice and its process group after the wall-clock budget elapsed with no vctrl_final reading. Reproducible per-point budget (see run_with_cap in sim/output-range/testbench/run.sh, #168) -- NOT an ngspice-reported error, and NOT an ad-hoc manual kill. This row is reported CAPPED, not ERROR. ====\n' \
            "${SIM_RUNCAP}" >>"${log}"
        fi
      fi
    else
      simenv_run_deck "${DECK}" "${WORK}" "${tag}" "${libs}" "${temp}" "${params[@]}" >/dev/null || true
    fi
    if [ ! -f "${log}" ] || ! grep -q "^vctrl_final" "${log}"; then
      # CAPPED is deliberately its own status rather than another flavour of
      # ERROR (#168). ERROR on this campaign means "the simulator reached a
      # verdict and it was a failure" -- the sf/27C `lo` rows abort in ~8
      # CPU-s naming a node. A budget termination is not a simulator verdict
      # at all, and the whole point of the cap is that a reader can tell the
      # two apart from the CSV alone rather than from the prose of a record.
      local nostatus="ERROR"
      if [ "${capfired}" -eq 1 ]; then nostatus="CAPPED"; fi
      echo "${corner},${temp},${vdd},${edge},${fout},${n},${fref},${nostatus},,,${k},${vctrl_ic},${seed_pos},,ERROR" >>"${outcsv}"
      return 0
    fi
  fi
  local tlock endok vfin
  tlock=$(simenv_meas "${log}" t_lock_last_rise)
  endok=$(simenv_meas "${log}" lock_at_end)
  vfin=$(simenv_meas "${log}" vctrl_final)
  local status="FAIL"
  if [ "${tlock}" != "nan" ] && [ "${endok}" != "nan" ]; then
    local held; held=$(awk -v e="${endok}" 'BEGIN{print (e+0 >= 1.5) ? 1 : 0}')
    [ "${held}" -eq 1 ] && status="PASS"
  fi
  # A corner whose open-loop table says this band cannot reach this edge
  # inside 0.9-2.7 V is reported as OUT-OF-WINDOW rather than PASS/FAIL: the
  # transient still ran and its vctrl_final is still reported, but scoring it
  # against a lock criterion would be scoring the loop for a target the VCO
  # band was never able to produce at that corner.
  #
  # This override is applied BEFORE the DN-branch guard below, deliberately:
  # the guard's FAIL-vs-SUSPECT split keys off whether the row reached lock,
  # and an OUT-OF-WINDOW row did not (it was never scored for it), so it takes
  # the SUSPECT branch -- the guard declines to attribute anything on a row
  # whose own status is already withheld.
  if [ "${seed_pos}" != "in" ]; then
    status="OUT-OF-WINDOW"
  fi
  # PFD DN-branch integration guard (#69) -- three-valued (PASS / FAIL /
  # SUSPECT / ERROR); see sim/lock-time/testbench/run.sh's run_one for why a
  # bare PASS/FAIL does not transfer to a campaign whose rows may legitimately
  # end the window still converging, and sim/README.md's "Closed-loop
  # internal-timestep bound" for what it guards.  This campaign is where the
  # guard was validated against a real violation: before #75 the `lo` edge ran
  # at a 2.0 ns internal ceiling and its DN branch never asserted.
  local dnl dnguard
  dnl=$(simenv_meas "${log}" dn_lvl)
  dnguard=$(awk -v d="${dnl}" -v acc="${ACC_DN_FRAC}" -v v="${vdd}" -v st="${status}" 'BEGIN{
    if (d !~ /^-?[0-9.]+([eE][-+]?[0-9]+)?$/) { print "ERROR"; exit }
    if (d + 0 >= acc * v) { print "PASS"; exit }
    print (st == "PASS") ? "FAIL" : "SUSPECT";
  }')
  echo "${corner},${temp},${vdd},${edge},${fout},${n},${fref},${status},${tlock},${vfin},${k},${vctrl_ic},${seed_pos},${dnl},${dnguard}" >>"${outcsv}"
}

case "${1:-}" in
  --one) shift; run_one "$@"; exit 0 ;;
esac
# Captured before the joblist loop below, which must not clobber "$@".
MODE="${1:-}"

# --------------------------------------------------------------------------
# Build the joblist (grid x edges), resolving each row's per-corner seed.
# Done before any simulation so `--plan` can print it for free.
# --------------------------------------------------------------------------
mkdir -p "${WORK}"
JOBLIST="${WORK}/jobs.txt"; : >"${JOBLIST}"
for corner in "${BUNDLES[@]}"; do
  for temp in "${TEMPS[@]}"; do
    for vdd in "${VDDS[@]}"; do
      for row in "${EDGES[@]}"; do
        read -r edge fout b2 b1 b0 n band <<<"${row}"
        seed=$(seed_for_corner "${corner}" "${temp}" "${vdd}" "${band}" "${fout}")
        vic="${seed%% *}"; pos="${seed##* }"
        if [ "${vic}" = "ERROR" ]; then
          echo "ERROR: no kvco_by_point.csv row for ${corner}/${temp}C/${vdd}V band ${band} (${pos})" >&2
          exit 1
        fi
        echo "${corner} ${temp} ${vdd} ${edge} ${fout} ${b2} ${b1} ${b0} ${n} ${vic} ${pos}" >>"${JOBLIST}"
      done
    done
  done
done
NJOBS=$(wc -l <"${JOBLIST}" | tr -d ' ')

if [ "${MODE}" = "--plan" ]; then
  echo "output-range: ${NJOBS} runs (full 45-point PVT grid x 2 band edges)"
  echo "corner temp vdd edge fout b2 b1 b0 n vctrl_ic seed_pos"
  cat "${JOBLIST}"
  awk '$11!="in"{c++} END{printf "output-range: %d row(s) OUT-OF-WINDOW (target unreachable inside 0.9-2.7 V at that corner)\n", c+0}' "${JOBLIST}"
  exit 0
fi

simenv_require_tools
cloop_require_netlist
cloop_assemble "${FRAGMENT}" "${DECK}"

if [ "${MODE}" = "--check" ]; then
  tmpdir=$(mktemp -d)
  trap 'rm -rf "${tmpdir}"' EXIT
  echo "${CSV_HEADER}" >"${tmpdir}/out.csv"
  chk=$(seed_for_corner "${CORNER}" "${TEMP}" "${VDD}" 1 10e6)
  run_one "${CORNER}" "${TEMP}" "${VDD}" lo 10e6 0 0 1 8 "${chk%% *}" "${tmpdir}/out.csv" "${chk##* }"
  cat "${tmpdir}/out.csv"
  exit 0
fi

RESULT_CSV="${WORK}/output_range_raw.csv"
echo "${CSV_HEADER}" >"${RESULT_CSV}"

JOBS="${SIM_JOBS:-1}"
echo "output-range: ${NJOBS} runs (full 45-point PVT grid x 2 band edges -- see run.sh header), ${JOBS} parallel"

export OUTCSV="${RESULT_CSV}"
# Same re-invocation pattern as sim/lock-time: each job re-enters this script
# via --one, so a single run is independently reproducible from the joblist.
# Each joblist line is 11 fields; the first 10 are run_one's leading
# arguments and the 11th (seed_pos) is passed through AFTER outcsv, as
# run_one's optional 12th argument, so the classification a row was scored
# under is carried by the row itself rather than re-derived at mint time.
# shellcheck disable=SC2016
xargs -P "${JOBS}" -L 1 \
  "${BASH:-/bin/bash}" -c 'exec "$0" --one "${@:1:10}" "${OUTCSV}" "${11}"' \
  "${HERE}/run.sh" \
  <"${JOBLIST}"

echo "output-range: wrote ${RESULT_CSV}"
cat "${RESULT_CSV}"

# --------------------------------------------------------------------------
# Mint the evidence record (sim/README.md convention).
# --------------------------------------------------------------------------
RID=$(simenv_record_id)
SNAPDIR="${EXP}/netlist-snapshots"
CORNERSDIR="${EXP}/corners/${RID}"
RECORDSDIR="${EXP}/records"
mkdir -p "${SNAPDIR}" "${CORNERSDIR}" "${RECORDSDIR}"

cp "${DECK}" "${SNAPDIR}/${RID}.spice"
SHA=$(simenv_sha256 "${SNAPDIR}/${RID}.spice")

while read -r corner temp vdd edge fout b2 b1 b0 n vic pos; do
  # Same row_tag() run_one wrote the run dir under (#168) -- rebuilding the
  # tag inline here used to drop the SIM_WINCAP suffix, so a sub-experiment
  # grid archived nothing at all while still minting a record. The seed
  # arguments are passed for the same reason: this loop's `vic` IS the value
  # xargs handed run_one for this row, so run_one and this loop cannot disagree
  # about the seed suffix either. (By construction `vic` came from
  # seed_for_corner, so the suffix is empty for every grid row and grid tags
  # are unchanged -- see row_tag.)
  tag=$(row_tag "${corner}" "${temp}" "${vdd}" "${edge}" \
                "${vic}" "$(( b2 * 4 + b1 * 2 + b0 ))" "${fout}") || exit 1
  cid="${corner}_${temp}c_${vdd}v_${edge}"
  simenv_archive_log "${WORK}" "${tag}" "${CORNERSDIR}" "${cid}"
  # tb_output_range.sp's `.control` block unconditionally `wrdata`s a small
  # vctrl/up/dn/lock/vwin waveform CSV (#49's Vctrl-anomaly prerequisite --
  # see that file's header comment). The pilot record committed both of its
  # two, and those waveforms are what 20260801-101734-5eb00db's internal-step
  # analysis was measured from. At THIS grid's scale (${NJOBS} runs) archiving
  # every one by default would commit far more than sim/README.md's retention
  # table asks be justified, so it follows sim/lock-time's convention: default
  # OFF, SIM_ARCHIVE_WAVEFORMS=1 to opt back in for a small targeted run.
  if [ "${SIM_ARCHIVE_WAVEFORMS:-0}" = "1" ] && [ -f "${WORK}/${tag}/waveform.csv" ]; then
    cp "${WORK}/${tag}/waveform.csv" "${CORNERSDIR}/${cid}_waveform.csv"
  fi
done <"${JOBLIST}"

RESULT_MD="${WORK}/result.md"
{
  echo "| Corner | Temp | VDD | Edge | Target f_out | N | Seed Vctrl | Status | vctrl_final | margin-to-0.9V | margin-to-2.7V | mean DN | DN guard |"
  echo "|---|---|---|---|---|---|---|---|---|---|---|---|---|"
  tail -n +2 "${RESULT_CSV}" \
    | sort -t, -k4,4 -k1,1 -k2,2n -k3,3n \
    | while IFS=, read -r corner temp vdd edge fout n fref status tlock vfin k vic pos dnl dnguard; do
    vfin_fmt="N/A"; mlo="N/A"; mhi="N/A"
    if [ -n "${vfin}" ] && [ "${vfin}" != "nan" ]; then
      vfin_fmt=$(awk -v v="${vfin}" 'BEGIN{printf "%.4g V", v}')
      mlo=$(awk -v v="${vfin}" 'BEGIN{printf "%.3g V", v-0.9}')
      mhi=$(awk -v v="${vfin}" 'BEGIN{printf "%.3g V", 2.7-v}')
    fi
    fout_fmt=$(awk -v f="${fout}" 'BEGIN{printf "%.4g MHz", f/1e6}')
    seed_fmt=$(awk -v v="${vic}" 'BEGIN{printf "%.4g V", v}')
    [ "${pos}" != "in" ] && seed_fmt="${seed_fmt} (${pos} band)"
    dnl_fmt="N/A"
    [ -n "${dnl}" ] && [ "${dnl}" != "nan" ] && dnl_fmt=$(awk -v d="${dnl}" 'BEGIN{printf "%.3g V", d}')
    echo "| ${corner} | ${temp}C | ${vdd}V | ${edge} | ${fout_fmt} | ${n} | ${seed_fmt} | ${status} | ${vfin_fmt} | ${mlo} | ${mhi} | ${dnl_fmt} | ${dnguard} |"
  done
} >"${RESULT_MD}"

# Per-edge counts. OUT-OF-WINDOW rows are counted separately from FAIL: they
# are a statement about the VCO band's reach at that corner (from #8's
# open-loop table), not about whether the loop locked.
edge_count() { awk -F, -v e="$1" -v s="$2" '$4==e && $8==s{c++} END{print c+0}' "${RESULT_CSV}"; }
edge_total() { awk -F, -v e="$1" '$4==e{c++} END{print c+0}' "${RESULT_CSV}"; }
LO_PASS=$(edge_count lo PASS);  LO_TOTAL=$(edge_total lo)
HI_PASS=$(edge_count hi PASS);  HI_TOTAL=$(edge_total hi)
LO_OOW=$(edge_count lo OUT-OF-WINDOW); HI_OOW=$(edge_count hi OUT-OF-WINDOW)
LO_ERR=$(edge_count lo ERROR);  HI_ERR=$(edge_count hi ERROR)
# CAPPED rows (#168) are tallied separately from ERROR, for the same reason
# run_one gives them their own status: a wall-clock budget termination is not
# a simulator verdict, and folding it into the ERROR count would put it back
# in the one bucket #168 exists to get it out of. A CAPPED row is only ever
# possible when SIM_RUNCAP is set, so an uncapped grid reports 0/0 here.
LO_CAP=$(edge_count lo CAPPED); HI_CAP=$(edge_count hi CAPPED)
CAP_LIST="(none)"
CAP_NOTE=""
if [ -n "${SIM_RUNCAP:-}" ]; then
  CAP_LIST=$(awk -F, '$8=="CAPPED"{printf "%s/%sC/%sV (%s)\n", $1, $2, $3, $4}' "${RESULT_CSV}" | paste -sd'; ' -)
  [ -z "${CAP_LIST}" ] && CAP_LIST="(none)"
  CAP_NOTE=" **This grid was run under a per-point wall-clock budget of \`SIM_RUNCAP=${SIM_RUNCAP}\` seconds** (see \`run_with_cap\` in \`sim/output-range/testbench/run.sh\`, #168), which is recorded in every row's work-directory tag. \`SIM_RUNCAP\` does NOT shorten the transient -- \`tstop\` is untouched -- so every row that completed under it is the same measurement an uncapped run would have produced. A row the budget terminated is reported \`CAPPED\`, never \`PASS\`/\`FAIL\`/\`ERROR\`: **${LO_CAP} \`lo\` + ${HI_CAP} \`hi\` row(s) hit the budget** -- ${CAP_LIST} -- and for those rows this record asserts nothing about whether the loop locks there, only that the simulator did not reach a verdict within ${SIM_RUNCAP} s of wall clock. Their archived \`corners/\` logs carry an explicit \`SIM_RUNCAP\` marker line saying so."
fi
OOW_LIST=$(awk -F, '$13!="in" && NR>1 {printf "%s/%sC/%sV (%s, %s)\n", $1, $2, $3, $4, $13}' "${RESULT_CSV}" | paste -sd'; ' -)
[ -z "${OOW_LIST}" ] && OOW_LIST="(none)"
OVERALL_SUMMARY="Across the full 45-point PVT grid at both band edges (${NJOBS} runs): the \`lo\` (10 MHz) edge reached a sustained in-window PASS on ${LO_PASS}/${LO_TOTAL} corners (${LO_OOW} OUT-OF-WINDOW, ${LO_ERR} ERROR, ${LO_CAP} CAPPED); the \`hi\` (200 MHz) edge on ${HI_PASS}/${HI_TOTAL} corners (${HI_OOW} OUT-OF-WINDOW, ${HI_ERR} ERROR, ${HI_CAP} CAPPED). OUT-OF-WINDOW rows: ${OOW_LIST}.${CAP_NOTE} The un-fabricated final Vctrl reading is reported for every row either way. **What a FAIL row means is decided per row by the DN-branch guard (#69), not asserted in advance:** on a guard-PASS row a FAIL means the transient window (see Methodology) was too short to observe sustained lock at that corner, NOT that the loop cannot reach that edge there; on a guard-SUSPECT row this record declines to attribute the FAIL to the window, the design, or the integration."

# PFD DN-branch guard tallies (#69). Columns are addressed positionally --
# see CSV_HEADER at the top of this script for the field map ($15 = dn_guard).
DNG_PASS=$(tail -n +2 "${RESULT_CSV}" | awk -F, '$15=="PASS"{c++} END{print c+0}')
DNG_FAIL=$(tail -n +2 "${RESULT_CSV}" | awk -F, '$15=="FAIL"{c++} END{print c+0}')
DNG_SUSPECT=$(tail -n +2 "${RESULT_CSV}" | awk -F, '$15=="SUSPECT"{c++} END{print c+0}')
DNG_ERROR=$(tail -n +2 "${RESULT_CSV}" | awk -F, '$15=="ERROR"{c++} END{print c+0}')
DNG_SUMMARY="**PFD DN-branch integration guard** (#69; \`sim/README.md\`'s \"Closed-loop internal-timestep bound\"): **${DNG_PASS} PASS / ${DNG_FAIL} FAIL / ${DNG_SUSPECT} SUSPECT / ${DNG_ERROR} ERROR** over the rows above, against a floor of ${ACC_DN_FRAC} of the rail. This campaign is where the guard was validated against a real violation: before #75 the \`lo\` edge derived its internal ceiling from its 10 MHz OUTPUT (\`1/(50*f_out)\` = 2.0 ns, ~6x the PFD's set pulse) and this measure read 6.6e-7 V -- three orders of magnitude under the floor, i.e. the DN branch never asserted, while nothing else in the verdict table looked wrong. The deck now takes the ceiling from \`SIMENV_CLOSED_LOOP_TMAX\` instead, so a **FAIL** verdict -- a row that reached lock while its DN branch stayed unresolved -- is the one that would mean the bound has been violated again. **SUSPECT is not that verdict and must not be read as one**: a row that did not reach lock inside its window never resolves the detector either, so the guard withholds attribution rather than indicting the ceiling. An \`OUT-OF-WINDOW\` row takes the same SUSPECT branch by construction (it never reached lock because it was never scored for it) -- see \`run_one\`."
RECORD="${RECORDSDIR}/${RID}.md"
{
  cat <<EOF
# Record ${RID}

- **Record ID**: ${RID}
- **Claim**: #12 (design-input claim, not a spec line -- spec #1 has not
  ratified yet) -- does the FULL closed loop (VCO #8, PFD/CP #9, loop filter
  #10, feedback divider #11) actually reach BOTH edges of the draft
  10-200 MHz v1 output band with real control-voltage headroom to the
  0.9-2.7 V usable window, complementing (not re-deriving) #8's open-loop
  \`vco-tuning-range\` characterization?
- **Netlist provenance**: schematic (\`design/pll_top.sch\`, exported by
  \`design/netlist.sh\` to \`design/netlist/pll_top.spice\`; the identical
  DUT \`sim/lock-time\` builds) ->
  \`sim/output-range/netlist-snapshots/${RID}.spice\` (exported subcircuit +
  testbench fragment, concatenated by \`sim/lib/pll_top_dut.sh\`), SHA-256
  \`${SHA}\`.
  **DUT changed at #159**: every \`sim/output-range\` record dated before
  that migration was taken against a different assembly of the same five
  blocks (\`sim/lib/assemble_closed_loop.sh\`, whose testbench wired the loop
  itself) and says so in its own provenance field. Those records stand as
  written; this one is not comparable to them netlist-for-netlist, only
  claim-for-claim.
- **Environment provenance**:
$(simenv_env_block "$(simenv_xschem_version) (batch netlist export of
    design/pll_top.sch via design/netlist.sh; the DUT netlist is a schematic
    export, not a hand-written deck)")
- **Corner matrix run**: the **FULL 45-point PVT grid** (5 MOS bundles x 3
  temperatures x 3 supplies) at both ratified output-band edges -- ${NJOBS}
  runs total. Extends the original deliberately-reduced single-corner pilot
  (\`sim/output-range/records/20260731-223426-640560e.md\`, 2 runs at
  typical/27C/3.30V) -- see **Supersedes** below for that record's standing
  after this one (this generated text does not assert either way, since the
  actual standing is decided by which \`SIM_SUPERSEDES\` id, if any, minted
  this specific record).
  - Axes not swept: passive process corners (held at
    \`res_typical\`/\`moscap_typical\`/\`mimcap_typical\`, the campaign's
    existing convention -- \`sim/lock-time\` does the same); VCO band code and
    N (one design point per edge, as the pilot chose them); Icp trim code
    (nominal "10" throughout).
- **Methodology / criteria / limitations**:
  - **Edge selection**: the draft ratified output band is 10-200 MHz
    (pending #1). Each edge's (VCO band code, N, f_ref) design point is read
    directly off #8's own
    \`sim/vco-tuning-range/corners/20260731-175947-0a12e6c/kvco_by_point.csv\`
    -- **not re-measured or re-derived here**, per the acceptance criteria's
    "cite, do not re-derive" requirement:
    - **Low edge (10 MHz)**: band 1, N=8 (f_ref=1.25 MHz).
    - **High edge (200 MHz)**: band 7, N=32 (f_ref=6.25 MHz).
  - **Per-corner seed (changed from the pilot, deliberately)**: the pilot
    hand-computed ONE \`vctrl_ic\` seed per edge, at typical/27C/3.30V
    (1.68 V / 1.32 V). This grid interpolates the seed **at each corner**
    from the same cited table by the same rule (linear between the two
    bracketing Vctrl rows) -- see \`seed_for_corner\` in
    \`sim/output-range/testbench/run.sh\`. The change is load-bearing rather
    than cosmetic: band 1 reaches 10 MHz anywhere from ~1.17 V
    (ss/125C/2.97V) to ~2.06 V (sf/-40C/3.63V) across this grid, so carrying
    the nominal seed everywhere would hand most corners a large initial
    control-voltage error and then give the loop the SAME short window to
    correct it -- a FAIL would then confound "the loop cannot reach this edge
    here" with "the seed was for a different corner". **Validated before use**:
    the programmatic rule reproduces the pilot's own hand-computed seeds at
    the pilot's corner (1.679 V vs. its stated 1.68 V for \`lo\`, 1.321 V vs.
    1.32 V for \`hi\`).
  - **OUT-OF-WINDOW rows**: at some corners the cited open-loop table shows
    the chosen band cannot produce the edge frequency anywhere inside the
    0.9-2.7 V usable Vctrl window. Those rows are seeded at the nearer rail,
    still simulated, and reported as \`OUT-OF-WINDOW\` rather than scored
    PASS/FAIL -- scoring the loop against a target its VCO band demonstrably
    cannot reach at that corner would misattribute an open-loop range
    limitation to the closed loop. This is a **real design-input finding**
    (that band/N choice does not cover that edge at that corner), and the
    affected corners are named in the Result summary.
  - **Why a seeded IC, and why that does not weaken the claim**: \`vctrl_ic\`
    is applied through the SAME released-clamp mechanism as
    \`sim/lock-time\` (see that campaign's Methodology for why a bare \`.ic\`
    does not work), released after a small \`t_force\`. Seeding near the
    expected lock point only shortens the transient this bench needs to
    reach steady state -- it does not assume the answer: the loop still has
    to close on its own from a real (small but nonzero) initial error, the
    real \`lock_detector\` (#11) still has to assert and hold, and the
    reported \`vctrl_final\` is the loop's own converged value, not the seed.
    A large-signal cold-start/worst-case-disturbance recovery to these same
    frequencies is \`sim/lock-time\`'s job (#12), not re-tested here.
  - **Lock criterion**: identical to \`sim/lock-time\` -- the real
    \`lock_detector\` (#11) wired to the PFD's UP/DN outputs; see that
    campaign's record for the full derivation (comparator window, implied
    frequency-settling band).
  - **Simulator settings**: identical \`.options\` to \`sim/lock-time\`
    (including the \`rshunt\`/\`itl4\` solver knobs #159 added for this DUT
    -- tolerances unchanged, see that campaign's deck for the bisection);
    transient print step \`1/(50*f_out)\` with an explicit
    **internal-timestep ceiling of ${SIMENV_CLOSED_LOOP_TMAX}**
    (the transient's 4th argument, \`SIMENV_CLOSED_LOOP_TMAX\` -- see
    \`sim/README.md\`'s "Closed-loop internal-timestep bound"). This is the
    first \`output-range\` grid taken at a compliant ceiling; every earlier
    record for this claim ran with the 4th argument absent, which put the
    \`lo\` edge at a 2 ns internal ceiling (see
    \`sim/lock-time/records/20260801-101734-5eb00db.md\`). Transient length is
    capped at 2 us for BOTH edges. **The 2 us cap is a much smaller number of
    reference cycles for \`lo\` than for \`hi\`, and this record says so
    rather than leaving it implicit**: \`lo\`'s 1.25 MHz reference gives only
    **~2.5 reference cycles** in 2 us; \`hi\`'s 6.25 MHz reference gives
    **~12.5 cycles**. \`lo\`'s rows are correspondingly the weaker of the two
    -- a handful of charge-pump pulses, not a settled trajectory -- and that
    is the single biggest limitation of this record.
  - **An anomaly carried forward from the pilot, reported not explained**:
    that record's raw ngspice log for \`lo\` (see its \`corners/\`) showed a
    complete, internally-consistent transient with real measurements,
    followed by ngspice re-entering its own analysis/gmin-stepping path a
    second time before the batch run exited -- observed on
    \`sim/lock-time\`'s \`relock\` row too (see that record's Methodology),
    not root-caused. This campaign's classification logic therefore does not
    gate completion on ngspice's own end-of-run banner -- see \`run_one\` in
    \`sim/output-range/testbench/run.sh\`.
  - **PFD DN-branch integration guard (#69)**: \`tb_output_range.sp\`
    measures \`dn_lvl\`, the mean DN level over the last 10 % of the window
    -- the same quantity \`sim/pll-top-smoke\`'s check 7 gates on, against
    the same floor. It is not a lock criterion; it is the per-row check that
    the internal-timestep ceiling was honoured, because a violation of that
    ceiling produces a confident, clean-looking "does not lock" rather than
    visible noise (\`sim/README.md\`'s "Closed-loop internal-timestep
    bound"). Scored three-valued -- \`PASS\` (DN asserts, so the row's own
    status means what it says), \`FAIL\` (reached lock with an unresolved
    detector), \`SUSPECT\` (did not reach lock AND did not resolve the
    detector, so the attribution is withheld) and \`ERROR\` (measurement
    did not land) -- because unlike \`pll-top-smoke\` this campaign has rows
    that can legitimately end the window still converging. Suppressing the
    guard on those rows was rejected: it would report \`N/A\` for exactly
    the row the guard exists to say something about. Full rationale in
    \`sim/lock-time/testbench/run.sh\`'s \`run_one\`. An \`OUT-OF-WINDOW\`
    row takes the \`SUSPECT\` branch by construction, since it never reached
    lock -- it was never scored for it.
  - **Limitations**: schematic-level, no parasitics; nominal-skew only
    (\`sw_stat_global = sw_stat_mismatch = 0\`, no Monte Carlo); one band/N
    design point per edge; the 2 us window is short for \`lo\` (above), so a
    \`lo\` FAIL row bounds nothing about whether that corner eventually
    locks; margin is reported per corner but the worst-margin corner is only
    as trustworthy as the window that produced it.$(simenv_method_note)
- **Statistical convention**: N/A -- corner-matrix claim, not a distribution
  claim.
- **Result**:
$(cat "${RESULT_MD}")

  ${OVERALL_SUMMARY}

  ${DNG_SUMMARY}
- **Links**:
  - Testbench: \`sim/output-range/testbench/tb_output_range.sp\`,
    \`sim/output-range/testbench/run.sh\`,
    \`sim/lib/pll_top_dut.sh\`
  - Design: \`design/pll_top.sch\` (which instantiates \`design/vco.sch\`,
    \`design/pfd_cp.sch\`, \`design/loop_filter.sch\`,
    \`design/divider_chain.sch\`, \`design/lock_detector.sch\`)
  - Consumed design-input evidence (read-only, cited not re-derived):
    \`${KVCO_CSV#"${REPO}"/}\`
  - Predecessor records (see **Supersedes** below for standing):
    \`sim/output-range/records/20260731-223426-640560e.md\` (single-corner
    pilot), \`sim/output-range/records/20260801-061907-67d7127.md\`
    (\`lo\`-edge waveform investigation -- its claim is the waveform
    diagnosis, not a corner-measurement standing this grid replaces, so it
    remains cited, not superseded, regardless of this record's own
    Supersedes field),
    \`sim/lock-time/records/20260801-101734-5eb00db.md\` (the
    internal-timestep-bound reconciliation this grid is the first
    \`output-range\` campaign to satisfy)
  - Netlist snapshot: \`sim/output-range/netlist-snapshots/${RID}.spice\`
  - Raw logs: \`sim/output-range/corners/${RID}/\`
- **Timestamp / author**: $(date -u +%Y-%m-%dT%H:%M:%SZ), ${SIM_AUTHOR:-agent-builder (issue #65)}
$(simenv_supersedes_field "${SIM_SUPERSEDES:-}")
EOF
} >"${RECORD}"

echo "output-range: wrote ${RECORD}"
echo "output-range: wrote ${SNAPDIR}/${RID}.spice"
echo "output-range: wrote ${CORNERSDIR}/ (${NJOBS} corner logs)"
