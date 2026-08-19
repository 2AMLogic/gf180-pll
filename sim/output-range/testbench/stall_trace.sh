#!/usr/bin/env bash
# gf180-pll :: output-range :: internal-timestep trace for a single point (#168)
#
# WHY THIS EXISTS. `sim/output-range`'s ff/27 C/3.30 V `hi` row does not finish:
# the #164 grid ran it for 151 CPU-minutes without reaching its 2 us stop time.
# ngspice in batch mode emits NOTHING between the operating-point printout and
# the end of the transient, so a run that stalls looks exactly like a run that
# is merely slow -- there is no way to answer "at what simulated time did it
# stop advancing, and by how much" from the campaign's own artifacts.
#
# This script answers that, and it is the instrument the #168 record cites.
#
# HOW IT KEEPS THE MEASUREMENT HONEST. The obvious cheap instrument -- re-run
# the point with a shorter `tstop` (SIM_WINCAP) and see which windows finish --
# does NOT work here, and the reason is worth stating because it is easy to get
# wrong: ngspice's first transient step is derived from `tstop`, so every
# distinct `tstop` walks a DIFFERENT sequence of timepoints. Short-window
# re-runs of this point abort at five different simulated times between 1.78 ns
# and 2.98 ns; none of them is the trajectory the real 2 us run takes.
#
# So this script does not touch `tstop`, `tstep`, `tmax`, `.options`, or any
# `.param`. It changes exactly one thing in the deck -- the `.control` block --
# replacing
#
#     tran $&c_tstep $&c_tstop 0 $&c_tmax
#     wrdata waveform.csv ...
#
# with a `stop after <n>` breakpoint before the identical `tran` line, then
# writes every vector it reached. Bounding the POINT COUNT rather than the
# window leaves the trajectory bit-identical to the campaign run's and just
# stops watching it after n accepted timepoints. Verify that with `--show-diff`.
#
# `--show-diff` also shows the campaign deck's `save` line dropped, which is
# the one difference that looks like it might matter and does not: `save`
# restricts which vectors ngspice STORES, never which it computes, so removing
# it changes memory use and nothing else. It has to go, because the whole
# point of the trace is to see the vectors the campaign deck does not keep.
# The check that all of this holds is empirical, not just argued: two traces
# of the same point at different `n` must agree on every timepoint they share.
# For the #168 point, n=260 and n=2000 both reach t=1.734625366e-09 s at index
# 259 -- run it twice and compare if you are changing this script.
#
# Usage:
#   ./stall_trace.sh <corner> <temp_c> <vdd> <edge> <fout> <b2> <b1> <b0> <n> \
#                    <vctrl_ic> <npoints> <outprefix>
#   ./stall_trace.sh --show-diff
#                     # print the deck delta (campaign deck vs. trace deck) and
#                     #   exit -- the audit that this instrument changes only
#                     #   the .control block
#
# The argument list up to <vctrl_ic> is deliberately identical to `run.sh
# --one`'s, so a traced point and a campaign point are spelled the same way.
#
# Example (the #168 point):
#   ./stall_trace.sh ff 27 3.30 hi 200e6 1 1 1 32 1.454 260 /tmp/i168
#
# Writes:
#   <outprefix>_timestep.csv  index,time_s,delta_s   -- one row per accepted
#                             #   internal timepoint: the timestep trace
#   <outprefix>_nodes.csv     name,excursion,v_first,v_last -- every vector
#                             #   ranked by how far it moves AFTER the
#                             #   timestep collapses, i.e. what is still
#                             #   ringing while the transient is not advancing
#   work/<tag>/trace.raw      the full ASCII rawfile (NOT committed --
#                             #   sim/README.md's retention policy)

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP="$(cd "${HERE}/.." && pwd)"
# shellcheck source=../../lib/simenv.sh
. "${HERE}/../../lib/simenv.sh"
# shellcheck source=../../lib/pll_top_dut.sh
. "${HERE}/../../lib/pll_top_dut.sh"

FRAGMENT="${HERE}/tb_output_range.sp"
WORK="${EXP}/work"
DECK="${WORK}/dut_output_range.sp"
TRACE_DECK="${WORK}/dut_output_range_trace.sp"
ICP_CODE=2
IUNIT=8u

# Build the trace deck: the campaign deck with its final `.control` block
# replaced. Everything above the block -- the DUT, the stimulus sources, the
# `.options`, the `.csparam`s, every `.measure` -- is copied byte for byte.
build_trace_deck() {
  cloop_require_netlist
  cloop_assemble "${FRAGMENT}" "${DECK}"
  awk '
    /^\.control/ { found = 1 }
    !found       { print }
  ' "${DECK}" >"${TRACE_DECK}.tmp"
  cat >>"${TRACE_DECK}.tmp" <<'EOF'
* ---- #168 stall-trace instrumentation (stall_trace.sh) ----
* The ONLY difference from the campaign deck. `tran` is issued with the
* identical arguments; the `stop after` breakpoint bounds the number of
* accepted timepoints instead of the window, so the trajectory is the
* campaign run's own. `write` dumps every vector, including `time`, so the
* achieved internal timestep can be read off directly.
.control
  set noaskquit
  set filetype=ascii
  stop after $&c_nstop
  tran $&c_tstep $&c_tstop 0 $&c_tmax
  echo STALL_TRACE: stopped after $&c_nstop accepted timepoints
  write trace.raw all
.endc
EOF
  # `c_nstop` alongside the deck's own `.csparam`s, so the stop count reaches
  # the control block by the same mechanism tstep/tstop/tmax already use.
  sed -e 's|^\.csparam c_tmax={tmax}$|.csparam c_tmax={tmax}\
.csparam c_nstop={nstop}|' "${TRACE_DECK}.tmp" >"${TRACE_DECK}"
  rm -f "${TRACE_DECK}.tmp"
  grep -q '^\.csparam c_nstop=' "${TRACE_DECK}" || {
    echo "ERROR: stall_trace.sh could not inject c_nstop -- has tb_output_range.sp's .csparam block moved?" >&2
    exit 1
  }
}

if [ "${1:-}" = "--show-diff" ]; then
  simenv_require_tools
  build_trace_deck
  echo "# campaign deck: ${DECK}"
  echo "# trace deck:    ${TRACE_DECK}"
  diff -u "${DECK}" "${TRACE_DECK}" || true
  exit 0
fi

[ "$#" -eq 12 ] || {
  sed -n '2,60p' "${BASH_SOURCE[0]}" >&2
  echo "ERROR: expected 12 arguments, got $#" >&2
  exit 1
}
corner="$1" temp="$2" vdd="$3" edge="$4" fout="$5"
b2="$6" b1="$7" b0="$8" n="$9" vctrl_ic="${10}" nstop="${11}" outprefix="${12}"

simenv_require_tools
build_trace_deck

band=$(( b2 * 4 + b1 * 2 + b0 ))
fref=$(awk -v f="${fout}" -v n="${n}" 'BEGIN{printf "%.8g", f/n}')
# Identical derivation to run.sh's run_one -- these must not drift, or the
# trace stops being a trace OF the campaign run.
tstop=$(awk -v fr="${fref}" 'BEGIN{t=20/fr; if (t>2e-6) t=2e-6; printf "%.6g", t}')
tstep=$(awk -v fo="${fout}" 'BEGIN{printf "%.6g", 1/(50*fo)}')
t_force=$(awk -v fr="${fref}" 'BEGIN{printf "%.6g", 0.02/fr}')

params=(
  "vsup=${vdd}" "fref=${fref}" "iunit=${IUNIT}"
  "vctrl_ic=${vctrl_ic}" "t_force=${t_force}"
  "tstep=${tstep}" "tstop=${tstop}" "tmax=${SIMENV_CLOSED_LOOP_TMAX}"
  "lockthresh=0.5*vsup" "nstop=${nstop}"
)
# shellcheck disable=SC2206
params+=( $(cloop_divider_params "${n}") )
# shellcheck disable=SC2207
params+=( $(cloop_band_params "${band}") )
# shellcheck disable=SC2207
params+=( $(cloop_trim_params "${ICP_CODE}") )

tag="ortrace_${corner}_${temp}c_${vdd}v_${edge}_tmax${SIMENV_CLOSED_LOOP_TMAX}_ic${vctrl_ic}_n${nstop}"
tag="${tag//./p}"
libs=$(simenv_bundle_libs "${corner}")
echo "stall_trace: ${tag} (tstop=${tstop} unchanged, bounded to ${nstop} timepoints)"
simenv_run_deck "${TRACE_DECK}" "${WORK}" "${tag}" "${libs}" "${temp}" "${params[@]}" >/dev/null || true

RAW="${WORK}/${tag}/trace.raw"
[ -f "${RAW}" ] || {
  echo "ERROR: no ${RAW} -- see ${WORK}/${tag}/ngspice.log" >&2
  exit 1
}

python3 - "${RAW}" "${outprefix}" <<'PY'
import sys

raw, prefix = sys.argv[1], sys.argv[2]
lines = open(raw).read().split("\n")
nvars = int(next(l for l in lines if l.startswith("No. Variables:")).split(":")[1])
npts = int(next(l for l in lines if l.startswith("No. Points:")).split(":")[1])
vstart = lines.index("Variables:") + 1
names = [lines[vstart + k].split()[1] for k in range(nvars)]

k = lines.index("Values:") + 1
data = []
for _ in range(npts):
    row = []
    for _ in range(nvars):
        row.append(float(lines[k].split()[-1]))
        k += 1
    data.append(row)
    while k < len(lines) and not lines[k].strip():
        k += 1

t = [r[0] for r in data]
with open(prefix + "_timestep.csv", "w") as f:
    f.write("index,time_s,delta_s\n")
    for i in range(npts):
        d = t[i] - t[i - 1] if i else 0.0
        f.write("%d,%.12e,%.6e\n" % (i, t[i], d))

# Where the ceiling was lost. Defined as the point after the LAST one taken at
# the internal-timestep ceiling, not the first small step: the run opens with a
# ramp of sub-ceiling steps as ngspice works up from its initial delta, and
# calling that a collapse would report the answer as t=0 on every run.
dmax = max((t[i] - t[i - 1]) for i in range(1, npts)) if npts > 1 else 0.0
at_ceiling = [i for i in range(1, npts) if (t[i] - t[i - 1]) >= 0.99 * dmax]
collapse = at_ceiling[-1] + 1 if at_ceiling and at_ceiling[-1] + 1 < npts else npts

with open(prefix + "_nodes.csv", "w") as f:
    f.write("# excursion = max-min of that vector over timepoints %d..%d,\n"
            "# i.e. after the internal timestep collapsed (simulated span %.4e s)\n"
            % (collapse, npts - 1, t[-1] - t[collapse] if collapse < npts else 0.0))
    f.write("name,excursion,value_at_collapse,value_at_last\n")
    rows = []
    for v in range(1, nvars):
        seg = [data[i][v] for i in range(collapse, npts)]
        if not seg:
            continue
        rows.append((max(seg) - min(seg), names[v], data[collapse][v], data[npts - 1][v]))
    for exc, nm, a, b in sorted(rows, reverse=True):
        f.write("%s,%.6e,%.6e,%.6e\n" % (nm, exc, a, b))

print("stall_trace: %d timepoints, t_end=%.6e s, last delta=%.4e s"
      % (npts, t[-1], t[-1] - t[-2] if npts > 1 else 0.0))
if collapse < npts:
    print("stall_trace: last timepoint at the %.4e s ceiling is index %d, "
          "t=%.6e s; the next step is %.4e s"
          % (dmax, collapse - 1, t[collapse - 1], t[collapse] - t[collapse - 1]))
    span = t[-1] - t[collapse]
    steps = npts - collapse
    if steps > 0 and span > 0:
        print("stall_trace: mean advance after collapse = %.4e s per timepoint"
              % (span / steps))
else:
    print("stall_trace: no timestep collapse within this many timepoints")
print("stall_trace: wrote %s_timestep.csv and %s_nodes.csv" % (prefix, prefix))
PY
