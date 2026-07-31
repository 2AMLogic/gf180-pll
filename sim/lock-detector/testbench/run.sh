#!/usr/bin/env bash
# gf180-pll :: lock-detector :: corner runner (issue #11, DR-002 Decision 4)
#
# Characterises design/lock_detector.sch -- the phase-error window comparator
# that produces the digital LOCK status output DR-002 Decision 4 puts in v1
# scope. One record is minted covering two sweeps of the same DUT:
#
#   grid   the full 45-point PVT grid at one representative phase error, which
#          is where the assert time, the deassert latency, the deep-in-lock /
#          deep-out-of-lock / frequency-error verdicts and the comparator
#          window t_win all come from.
#   window a phase-error ladder at five corners chosen to bracket the grid,
#          walking the error across the comparator window so its EDGES are
#          measured rather than inferred from two far-apart points.
#
# Usage:
#   ./run.sh                 # both sweeps; mints one record
#   ./run.sh --check         # nominal corner only, to stdout
#   SIM_JOBS=8 ./run.sh      # cap parallelism
#
#   SIM_SUPERSEDES=<record-id> SIM_SUPERSEDES_NOTE='<why>' ./run.sh
#                            mint the record with a **Supersedes** field naming
#                            the record this run replaces (sim/README.md ::
#                            "Status / supersession language").  Set at mint
#                            time on purpose -- editing the field into a
#                            generated record afterwards is a record rewrite.
#
# The DUT netlist comes from design/netlist/lock_detector.spice, which
# design/netlist.sh exports from design/lock_detector.sch. This runner freezes
# whatever is committed there; it does not regenerate it.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP="$(cd "${HERE}/.." && pwd)"
ROOT="$(cd "${EXP}/../.." && pwd)"
# shellcheck source=../../lib/simenv.sh
. "${HERE}/../../lib/simenv.sh"

WORK="${EXP}/work"
DUT="${WORK}/dut_lock.sp"
NETLIST="${ROOT}/design/netlist/lock_detector.spice"

# Fixed stimulus parameters, shared by every run so records stay comparable.
#   KFREF   reference rate the detector is characterised at. 25 MHz is the top
#           of the draft reference range, so the ~1.5 us integrator hold-off
#           spans tens of reference cycles -- see the record's limitation on
#           the low end of the reference range.
#   KTRST   PFD reset-path overlap: the interval where UP and DN are BOTH
#           high. It cancels in the DUT's input XOR, which is why it is
#           modelled explicitly rather than assumed away.
#   KTERR   phase error for the grid sweep. 4 ns is comfortably outside the
#           ~1.2 ns comparator window, so the grid point is a genuine
#           out-of-window case at every corner rather than one that flips
#           verdict with PVT (the window ladder is what probes the edge).
#   KTBIG   phase error the XE copy is kicked to at KTPERT, to test deassert.
#   KTPERT  when the XE copy is kicked out of lock. It has to sit clear of the
#           slowest corner's assert time, or the copy would be kicked before it
#           had locked and the deassert test would measure nothing. 2.40 us is
#           chosen against a slowest measured assert of ~1.9 us (slow-PMOS
#           bundles at 125 C / 2.97 V, since a weak PMOS is what charges the
#           integrating node).
KFREF=25e6
KTRST=1n
KTERR=4n
KTBIG=8n
KTPERT=2.40u
KTSTOP=3.40u
KTSTEP=200p

# Phase-error ladder for the window sweep, seconds. Spans well inside to well
# outside the nominal ~1.2 ns window.
WINDOW_LADDER=(0.2n 0.5n 0.8n 1.0n 1.2n 1.5n 2.0n 3.0n 5.0n 10.0n)

# Corners for the window sweep: nominal plus the four grid extremes.
WINDOW_CORNERS=("typical 27 3.30" "ss 125 2.97" "ss -40 3.63" "ff 125 2.97" "ff -40 3.63")

build_dut() {
  mkdir -p "${WORK}"
  [ -f "${NETLIST}" ] || {
    echo "ERROR: ${NETLIST} missing -- run design/netlist.sh" >&2
    exit 1
  }
  # Swapped in only if the content actually changed, so an unchanged DUT keeps
  # its mtime and run_deck_soft's cache survives a restart.
  local tmp="${DUT}.$$.new"
  cat "${NETLIST}" "${HERE}/tb_lock_detector.sp" >"${tmp}"
  if cmp -s "${tmp}" "${DUT}"; then rm -f "${tmp}"; else mv "${tmp}" "${DUT}"; fi
}

mktag() { local t="$*"; t="${t// /_}"; t="${t//./p}"; t="${t//-/m}"; echo "${t}"; }

# A copy that never asserts produces a FAILED `.meas`, and that is the PASS
# condition for the deep-out-of-lock and frequency-error copies. So the
# completion test is "did the transient finish", not "was the log clean".
run_deck_soft() {
  local deck="$1" workdir="$2" tag="$3"
  local rundir="${workdir}/${tag}" log="${workdir}/${tag}/ngspice.log"
  local sig="$*"
  # Reuse a completed run only if BOTH the deck it was produced from is
  # unchanged (mtime) and the exact argument list -- corner, temperature, every
  # injected .param -- is identical (signature file). Sweeps here are hours long
  # on a shared machine, so a resumable runner is worth having; caching on the
  # deck alone would silently reuse a run taken at different parameters, which
  # is precisely the kind of quiet wrong number sim/README.md exists to prevent.
  # SIM_FORCE=1 forces a cold run.
  if [ -z "${SIM_FORCE:-}" ] && [ -f "${log}" ] && [ "${log}" -nt "${deck}" ] \
     && [ "$(cat "${rundir}/.sig" 2>/dev/null)" = "${sig}" ] \
     && grep -q "Total analysis time" "${log}" 2>/dev/null; then
    return 0
  fi
  simenv_run_deck "$@" >/dev/null 2>&1 || true
  if grep -q "Total analysis time" "${log}" 2>/dev/null; then
    printf '%s' "${sig}" >"${rundir}/.sig"
    return 0
  fi
  echo "ERROR: ngspice did not complete a transient for tag=${tag} (see ${log})" >&2
  return 1
}

LOCK_HEADER="process,temp_c,vdd_v,terr_s,twin_r_s,twin_f_s,t_assert_swept_s,lock_swept,t_assert_inlock_s,lock_inlock,lock_bigerr,lock_freqerr,t_assert_pert_s,t_deassert_pert_s,lock_pert_before,lock_pert_after,i_supply_a,pass"

run_one() {
  local corner="$1" temp="$2" vdd="$3" terr="$4"
  local tag; tag=$(mktag "lk ${corner} ${temp} ${vdd} ${terr}")
  run_deck_soft "${DUT}" "${WORK}" "${tag}" "${corner}" "${temp}" \
    "vsup=${vdd}" "kfref=${KFREF}" "ktrst=${KTRST}" "kterr=${terr}" \
    "kterrbig=${KTBIG}" "ktpert=${KTPERT}" "ktstep=${KTSTEP}" "ktstop=${KTSTOP}"
  local log="${WORK}/${tag}/ngspice.log"
  local twr twf taa tab tae tde la lb lc ld le lep ia
  twr=$(simenv_meas "${log}" twin_r); twf=$(simenv_meas "${log}" twin_f)
  taa=$(simenv_meas "${log}" ta_asrt); tab=$(simenv_meas "${log}" tb_asrt)
  tae=$(simenv_meas "${log}" te_asrt); tde=$(simenv_meas "${log}" te_deas)
  la=$(simenv_meas "${log}" la_lvl); lb=$(simenv_meas "${log}" lb_lvl)
  lc=$(simenv_meas "${log}" lc_lvl); ld=$(simenv_meas "${log}" ld_lvl)
  le=$(simenv_meas "${log}" le_lvl); lep=$(simenv_meas "${log}" le_pre)
  ia=$(simenv_meas "${log}" iavg)
  awk -v c="${corner}" -v t="${temp}" -v v="${vdd}" -v te="${terr}" \
      -v twr="${twr}" -v twf="${twf}" -v taa="${taa}" -v tab="${tab}" \
      -v tae="${tae}" -v tde="${tde}" -v la="${la}" -v lb="${lb}" -v lc="${lc}" \
      -v ld="${ld}" -v le="${le}" -v lep="${lep}" -v ia="${ia}" \
      -v tp="$(awk -v x="${KTPERT}" 'BEGIN{sub(/u$/,"",x); printf "%.6g", x*1e-6}')" '
    function abs(x) { return x < 0 ? -x : x }
    # A settled digital level: high above 90% of the rail, low below 10%.
    # Anything between is a chattering flag and is reported as CHATTER rather
    # than rounded to a verdict.
    function lvl(x, vv) {
      if (x == "nan") return "?"
      if (x + 0 > 0.9 * vv) return "HIGH"
      if (x + 0 < 0.1 * vv) return "LOW"
      return "CHATTER"
    }
    function num(x) { return (x == "nan") ? "nan" : sprintf("%.6g", x + 0) }
    # The ladder is written with SPICE suffixes ("0.2n"); awk would silently
    # read that as 0.2, so the suffix is converted rather than truncated.
    function secs(x) { sub(/n$/, "", x); return x * 1e-9 }
    BEGIN {
      sw = lvl(la, v); il = lvl(lb, v); be = lvl(lc, v)
      fe = lvl(ld, v); pa = lvl(le, v); pb = lvl(lep, v)
      # Acceptance for a run: deep in lock asserts and stays asserted; a large
      # static phase error never asserts; a frequency error never asserts; and
      # the perturbed copy is asserted before the kick and deasserted after.
      # The perturbed copy must have asserted BEFORE the kick and be deasserted
      # after it. "Before" is tested as assert-time < kick-time rather than as
      # a level averaged over the run-up to the kick: at the slowest corners the
      # assert transition itself falls inside any such averaging window and
      # reads as CHATTER, which is an artefact of the window, not of the flag.
      # The level is still reported, as context for exactly that case.
      ok = (il == "HIGH" && tab != "nan" &&
            be == "LOW" && lc != "nan" &&
            fe == "LOW" &&
            tae != "nan" && tae + 0 < tp + 0 && pa == "LOW" && tde != "nan")
      printf "%s,%s,%s,%.6g,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n",
             c, t, v, secs(te), num(twr), num(twf), num(taa), sw, num(tab), il,
             be, fe, num(tae), num(tde), pb, pa, num(abs(ia)),
             (ok ? "PASS" : "FAIL")
    }'
}

case "${1:-}" in
  --one) shift; run_one "$@"; exit 0 ;;
esac

simenv_require_tools
build_dut

if [ "${1:-}" = "--check" ]; then
  echo "${LOCK_HEADER}"
  run_one typical 27 3.30 "${KTERR}"
  exit 0
fi

JOBS=$(simenv_jobs)
mkdir -p "${WORK}"

GRID_JOBS="${WORK}/jobs_grid.txt"; : >"${GRID_JOBS}"
for corner in "${SIMENV_MOS_CORNERS[@]}"; do
  for temp in "${SIMENV_TEMPS[@]}"; do
    for vdd in "${SIMENV_VDDS[@]}"; do
      echo "${corner} ${temp} ${vdd} ${KTERR}" >>"${GRID_JOBS}"
    done
  done
done
WIN_JOBS="${WORK}/jobs_win.txt"; : >"${WIN_JOBS}"
for cs in "${WINDOW_CORNERS[@]}"; do
  for te in "${WINDOW_LADDER[@]}"; do
    echo "${cs} ${te}" >>"${WIN_JOBS}"
  done
done

ALL_JOBS="${WORK}/jobs_all.txt"
cat "${GRID_JOBS}" "${WIN_JOBS}" | sort -u >"${ALL_JOBS}"
NPOINTS=$(wc -l <"${ALL_JOBS}" | tr -d ' ')
echo "lock-detector: ${NPOINTS} points ($(wc -l <"${GRID_JOBS}" | tr -d ' ') grid + $(wc -l <"${WIN_JOBS}" | tr -d ' ') window ladder, deduplicated), ${JOBS} jobs"

ROWS="${WORK}/rows.csv"; : >"${ROWS}"
# shellcheck disable=SC2016
xargs -P "${JOBS}" -L 1 "${BASH:-/bin/bash}" -c 'exec "$0" --one "$@"' \
  "${HERE}/run.sh" <"${ALL_JOBS}" >>"${ROWS}"
GOT=$(wc -l <"${ROWS}" | tr -d ' ')
[ "${GOT}" -eq "${NPOINTS}" ] || { echo "ERROR: expected ${NPOINTS} rows, got ${GOT}" >&2; exit 1; }
sort -t, -k1,1 -k2,2n -k3,3n -k4,4 "${ROWS}" -o "${ROWS}"

# ===========================================================================
# Record (sim/README.md convention)
# ===========================================================================
RID=$(simenv_record_id)
SNAPDIR="${EXP}/netlist-snapshots"; CORNERSDIR="${EXP}/corners/${RID}"
RECORDSDIR="${EXP}/records"
mkdir -p "${SNAPDIR}" "${CORNERSDIR}" "${RECORDSDIR}"
cp "${DUT}" "${SNAPDIR}/${RID}.spice"
SHA=$(simenv_sha256 "${SNAPDIR}/${RID}.spice")

while read -r corner temp vdd terr; do
  el=$(awk -v e="${terr}" 'BEGIN{gsub(/[a-z]/,"",e); printf "e%04d", e*100}')
  simenv_archive_log "${WORK}" "$(mktag "lk ${corner} ${temp} ${vdd} ${terr}")" \
    "${CORNERSDIR}" "$(simenv_corner_id "${el}-${corner}" "${temp}" "${vdd}")"
done <"${ALL_JOBS}"

CSV="${CORNERSDIR}/lock_corners.csv"
{
  simenv_provenance "lock-detector" "${RID}" \
    "design/lock_detector.sch -> design/netlist/lock_detector.spice + sim/lock-detector/testbench/tb_lock_detector.sp" \
    "45-point PVT grid at terr=${KTERR}; plus a 10-step phase-error ladder at 5 corners"
  cat <<EOF
# Stimulus models the tri-state PFD interface: UP high for (terr + t_reset),
#   DN high for t_reset, both falling together, so XOR(UP,DN) is high for
#   exactly terr. t_reset = ${KTRST}, reference rate = ${KFREF} Hz.
# twin_r_s / twin_f_s: rise/fall delay of a bare delaywin_3v3 with an ideal
#   step in = the comparator window itself.
# *_swept: the XA copy, driven at the terr of this row.
# *_inlock: the XB copy, terr = 0 (reset overlap only) -- must assert.
# lock_bigerr: the XC copy, static phase error = Tref/4 -- must never assert.
# lock_freqerr: the XD copy, feedback train 25% slow, so the error pulse beats
#   through every width from 0 to Tref -- must never assert.
# *_pert: the XE copy, terr = 0 until ${KTPERT} then kicked to ${KTBIG}.
#   lock_pert_before must be HIGH and lock_pert_after LOW.
# Levels are classified HIGH (>90% rail) / LOW (<10% rail) / CHATTER
#   (in between, i.e. the flag is toggling within the averaging window).
# i_supply_a: total for five DUT copies plus the testbench's OR gates and the
#   bare window element on the same rail -- an upper bound on one copy x 5,
#   not a per-copy figure.
EOF
  echo "${LOCK_HEADER}"; cat "${ROWS}"
} >"${CSV}"

SUM=$(grep -v '^#' "${CSV}" | tail -n +2 | awk -F, '
  { n++; if ($18 == "FAIL") f++
    if (twmin == "" || $5 + 0 < twmin) twmin = $5 + 0
    if (twmax == "" || $5 + 0 > twmax) { twmax = $5 + 0; twc = $1 "/" $2 "C/" $3 "V" }
    if ($9 != "nan") {
      if (amin == "" || $9 + 0 < amin) amin = $9 + 0
      if (amax == "" || $9 + 0 > amax) { amax = $9 + 0; ac = $1 "/" $2 "C/" $3 "V" }
    }
    if ($14 != "nan") {
      d = $14 - '"${KTPERT%u}"'e-6
      if (dmax == "" || d > dmax) { dmax = d; dc = $1 "/" $2 "C/" $3 "V" }
    }
    if ($11 != "LOW" || $12 != "LOW") bad++
  }
  END { printf "%d|%d|%.6g|%.6g|%s|%.6g|%.6g|%s|%.6g|%s|%d",
        n, f + 0, twmin, twmax, twc, amin, amax, ac, dmax, dc, bad + 0 }')
S_N=$(echo "${SUM}" | cut -d'|' -f1)
S_FAIL=$(echo "${SUM}" | cut -d'|' -f2)
S_TWMIN=$(echo "${SUM}" | cut -d'|' -f3)
S_TWMAX=$(echo "${SUM}" | cut -d'|' -f4)
S_TWC=$(echo "${SUM}" | cut -d'|' -f5)
S_AMIN=$(echo "${SUM}" | cut -d'|' -f6)
S_AMAX=$(echo "${SUM}" | cut -d'|' -f7)
S_AC=$(echo "${SUM}" | cut -d'|' -f8)
S_DMAX=$(echo "${SUM}" | cut -d'|' -f9)
S_DC=$(echo "${SUM}" | cut -d'|' -f10)
S_BAD=$(echo "${SUM}" | cut -d'|' -f11)

# Window edge: for each window-ladder corner, the largest phase error that
# still left the swept copy asserted, and the smallest that did not.
# Only the ladder corners can bracket a window edge -- a grid corner has a
# single phase-error point and would contribute a meaningless "did not assert
# from <that one point>" row. Corners are therefore included only if the run
# actually stepped three or more distinct phase errors there.
WINTAB=$(grep -v '^#' "${CSV}" | tail -n +2 | awk -F, '
  { key = $1 "/" $2 "C/" $3 "V"
    e = $4 + 0
    if (!((key SUBSEP e) in pt)) { pt[key SUBSEP e] = 1; npts[key]++ }
    if ($8 == "HIGH") { if (!(key in hi) || e > hi[key]) hi[key] = e }
    else              { if (!(key in lo) || e < lo[key]) lo[key] = e }
    seen[key] = 1 }
  END { for (k in seen) if (npts[k] >= 3)
          printf "  | %s | %s | %s |\n", k,
            ((k in hi) ? sprintf("%.3g ns", hi[k] * 1e9) : "none, down to the smallest step"),
            ((k in lo) ? sprintf("%.3g ns", lo[k] * 1e9) : "none, up to the largest step") }' | sort)

cat >"${RECORDSDIR}/${RID}.md" <<EOF
# Record ${RID}

- **Record ID**: ${RID}
- **Claim**: #11 -> DR-002 Decision 4 (design input, not a spec line) -- does
  the window-comparator lock detector assert once the phase error has stayed
  inside its window, refuse to assert on a large static phase error or on a
  frequency error, and deassert when the loop is deliberately perturbed out
  of lock -- at every PVT corner? And where are the EDGES of that window,
  measured rather than inferred? DR-002 Decision 4 puts a digital \`lock\`
  output in v1 scope as a passive monitor (no band-search or calibration
  FSM), and names #12's closed-loop testbench as the consumer of the signal.
- **Netlist provenance**: schematic (\`design/lock_detector.sch\`, exported by
  \`design/netlist.sh\` to \`design/netlist/lock_detector.spice\`) ->
  \`sim/lock-detector/netlist-snapshots/${RID}.spice\` (exported subcircuit +
  testbench, concatenated), SHA-256 \`${SHA}\`
- **Environment provenance**:
$(simenv_env_block)
- **Corner matrix run**: ${S_N} points in two deduplicated sweeps
  - **Grid**: all 45 PVT points (5 MOS bundles x 3 temperatures x 3 supplies)
    at a fixed phase error of ${KTERR}, which is well outside the nominal
    window so the grid point is an unambiguous out-of-window case at every
    corner.
  - **Window ladder**: phase error stepped over
    ${WINDOW_LADDER[*]} at five corners --
    ${WINDOW_CORNERS[0]}, ${WINDOW_CORNERS[1]}, ${WINDOW_CORNERS[2]},
    ${WINDOW_CORNERS[3]}, ${WINDOW_CORNERS[4]} (nominal plus the four
    slow/fast x cold/hot x low/high-supply extremes) -- so the window edge is
    bracketed at the corners that move it most.
  - Bundles (-> \`.lib\` sections of sm141064.ngspice): \`typical\` -> typical;
    \`ff\` -> ff; \`ss\` -> ss; \`fs\` -> fs; \`sf\` -> sf
  - Temperature: -40 C, 27 C, 125 C. Supply: 2.97 / 3.30 / 3.63 V.
  - **Axes not swept**: passive corner sections N/A -- the integrating
    capacitor is a MOS capacitor built from \`nfet_03v3\` (DR-002 Decision 3:
    3.3 V thick-oxide devices only), so it moves with the MOS bundle already
    swept and there is no independent \`mimcap_*\` / \`moscap_*\` axis in this
    DUT. There are no poly resistors.
  - **Reference rate not swept**: characterised at ${KFREF} Hz only; see the
    limitation on the low end of the reference range below.
- **Methodology / criteria / limitations**:
  - Stimulus models the tri-state PFD's UP/DN pair: with the reference edge
    leading the feedback edge by tau, UP is high for tau + t_reset and DN for
    t_reset (${KTRST}), both falling on the reset path, so the DUT's input XOR
    sees exactly tau and the common reset overlap cancels. That cancellation
    is the reason the DUT starts with an XOR rather than looking at UP alone,
    and modelling the overlap explicitly is what tests it.
  - Five independent DUT copies share each transient: swept phase error;
    deep in lock (tau = 0); deep out of lock (static tau = Tref/4);
    frequency error (feedback train 25% slow, so the error pulse beats
    through every width from 0 to Tref); and a copy that starts in lock and
    is kicked to a sustained tau = ${KTBIG} at t = ${KTPERT}.
  - Every integrating node is forced to 0 V at t=0 (\`.ic\`), so each copy
    starts NOT locked and has to earn the assertion inside the run rather
    than inherit it from the DC operating point.
  - Verdicts are taken from levels averaged over the last 10% of the run and
    classified HIGH (>90% of the rail) / LOW (<10%) / **CHATTER** (anything
    between). A chattering flag is reported as chatter, not rounded to a
    verdict -- that distinction is the whole point of putting hysteresis (the
    Schmitt readout) in the DUT.
  - A run PASSes only if all four behavioural checks hold at once: deep in
    lock asserts, large static error never asserts, frequency error never
    asserts, and the perturbed copy is asserted before the kick and
    deasserted after. "Asserted before the kick" is tested as assert-time <
    kick-time rather than as a level averaged over the run-up to the kick,
    because at the slowest corners the assert transition itself lands inside
    any such averaging window and reads as CHATTER -- an artefact of the
    window, not of the flag. The level is still reported alongside, so that
    case is visible rather than smoothed away.
  - Simulator settings: \`.tran ${KTSTEP} ${KTSTOP}\`, \`reltol 1e-3\`,
    \`abstol 1e-10\`.
  - **Limitation -- low end of the reference range.** The assert time
    measured below is set by a weak pull-up charging a MOS capacitor, i.e. an
    absolute time, not a count of reference cycles. Reliable deassert
    requires that hold-off to be much longer than one reference period, so
    that a single out-of-window pulse per reference cycle keeps the node
    down. At the ${KFREF} Hz characterised here that is tens of reference
    cycles and holds with margin; extrapolating the same hold-off to the
    1 MHz bottom of the draft reference range leaves only of order one
    reference period, where the flag would be expected to chatter. **That
    extrapolation is a hand argument from the measured hold-off, not a
    measured result** -- this record makes no claim at 1 MHz. Scaling the
    integrating capacitor is a purely geometric fix, and #1/#12 should settle
    the reference range this detector is specified over.
  - **Limitation -- absolute window.** The comparator window t_win is an
    inverter-chain delay, so it is an absolute time and its ratio to the
    reference period changes across the reference range. The phase-error
    band the flag implies is therefore a fixed number of nanoseconds, not a
    fixed fraction of a cycle.
  - **Limitation -- schematic-level.** No extracted parasitics; the
    integrating node is high-impedance and its post-layout capacitance and
    leakage will move both the assert time and the window. #18 must re-take
    this.
  - Statistical switches: \`sw_stat_global = sw_stat_mismatch = 0\`.
- **Statistical convention**: N/A -- corner-matrix claim, not a distribution
  claim. Device mismatch on the Schmitt trigger's trip points would move the
  assert threshold and is a Monte Carlo question this record does not answer.
- **Result**:

  | Metric | Value | Corner |
  |---|---|---|
  | points run | ${S_N} | -- |
  | points failing the four-check acceptance | ${S_FAIL} | -- |
  | points where a large static error or a frequency error asserted | ${S_BAD} | -- |
  | comparator window t_win (min .. max over all points) | ${S_TWMIN} .. ${S_TWMAX} s | max at ${S_TWC} |
  | assert time from cold start, deep in lock (min .. max) | ${S_AMIN} .. ${S_AMAX} s | max at ${S_AC} |
  | worst deassert latency after the perturbation | ${S_DMAX} s | ${S_DC} |

  **Window edges** -- largest phase error that still left the swept copy
  asserted, and smallest that did not, per window-ladder corner:

  | Corner | asserted up to | did not assert from |
  |---|---|---|
${WINTAB}

  Full per-point table:
  \`sim/lock-detector/corners/${RID}/lock_corners.csv\`.

  **Conclusion**: the "points failing the four-check acceptance" row is the
  headline -- 0 means the flag asserts in lock, refuses to assert on both a
  large static phase error and a frequency error, and deasserts on a
  deliberate perturbation, at every corner. The window-edge table is the
  quantity #12 needs in order to state what "locked" means when it consumes
  this signal as a pass/fail: the flag asserts for phase errors below the
  left column and not above the right column, and that band moves over PVT by
  the t_win spread above.
- **Links**:
  - Testbench: \`sim/lock-detector/testbench/tb_lock_detector.sp\`
  - Schematic: \`design/lock_detector.sch\`
  - Netlist snapshot: \`sim/lock-detector/netlist-snapshots/${RID}.spice\`
  - Raw logs: \`sim/lock-detector/corners/${RID}/\`
  - Extracted metrics: \`sim/lock-detector/corners/${RID}/lock_corners.csv\`
- **Timestamp / author**: $(date -u +%Y-%m-%dT%H:%M:%SZ), agent-builder (issue #11)
$(simenv_supersedes_field "${SIM_SUPERSEDES:-}")
EOF

echo "lock-detector: wrote ${RECORDSDIR}/${RID}.md"
echo "lock-detector: wrote ${CSV}"
echo "lock-detector: FAIL=${S_FAIL}/${S_N}"
