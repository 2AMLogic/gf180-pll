#!/usr/bin/env bash
# gf180-pll :: devchar-cp :: corner runner
#
# Sweeps tb_cp_mirror.sp over the full repo PVT grid:
#   process {typical, ff, ss, fs, sf} x temp {-40, 27, 125} C x supply
#   {2.97, 3.30, 3.63} V  = 45 points, six candidate mirror stacks per point.
#
# Usage:
#   ./run.sh                 # full grid -> results/cp_summary.csv + cp_curves.csv
#   ./run.sh --check         # nominal corner only, summary printed to stdout
#   SIM_JOBS=4 ./run.sh      # cap parallelism
#
# Extraction (all from the DC output I-V of each stack, 10 mV steps):
#   isat            deep-saturation output current (N: at Vout=Vdd, P: at Vout=0)
#   ro(Vout)        central difference dVout/dIout on the 10 mV grid
#   vcomp_i1pct     output voltage at which |Iout| first reaches 99 % of isat
#   vcomp_ro50      output voltage at which ro falls to 50 % of its mid-rail
#                   value -- the boundary that actually matters for a cascode,
#                   whose current stays accurate well past the point where its
#                   output resistance has collapsed
#   headroom_*      the same boundary expressed as distance from the stack's own
#                   rail (ground for the N sinks, Vdd for the P sources)

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/simenv.sh
. "${HERE}/../lib/simenv.sh"

DECK="${HERE}/tb_cp_mirror.sp"
WORK="${HERE}/work"
OUT_SUMMARY="${HERE}/results/cp_summary.csv"
OUT_CURVES="${HERE}/results/cp_curves.csv"

SUMMARY_HEADER="stack,process,temp_c,vdd_v,iref_a,isat_a,iout_mid_a,gain_mid,ro_30pct_ohm,ro_50pct_ohm,ro_70pct_ohm,vcomp_i1pct_v,vcomp_i5pct_v,vcomp_ro50_v,headroom_i1pct_v,headroom_ro50_v,vth_ref_v,vdsat_ref_v"
CURVES_HEADER="stack,process,temp_c,vdd_v,vout_v,iout_a,ro_ohm"

IREF="20e-6"
# Decimation of the committed curve file: the sweep runs at 10 mV, the archived
# curve is every 5th point (50 mV), which still resolves every knee here.
CURVE_DECIMATE=5

# --------------------------------------------------------------------------
# Single corner point.
#   run_one <corner> <temp> <vdd> <summary-out> <curves-out>
# --------------------------------------------------------------------------
run_one() {
  local corner="$1" temp="$2" vdd="$3" sfile="$4" cfile="$5"
  local tag="${corner}_T${temp}_V${vdd}"
  tag="${tag//./p}"
  tag="${tag//-/m}"

  simenv_run_deck "${DECK}" "${WORK}" "${tag}" "${corner}" "${temp}" "vsup=${vdd}" >/dev/null
  local rundir="${WORK}/${tag}"

  local opn opp
  opn=$(awk '/^OPN /{print $3" "$5; exit}' "${rundir}/ngspice.log")
  opp=$(awk '/^OPP /{print $3" "$5; exit}' "${rundir}/ngspice.log")
  if [ -z "${opn}" ] || [ -z "${opp}" ]; then
    echo "ERROR: missing operating-point record for tag=${tag}" >&2
    return 1
  fi

  awk -v corner="${corner}" -v temp="${temp}" -v vdd="${vdd}" -v iref="${IREF}" \
      -v opn="${opn}" -v opp="${opp}" -v dec="${CURVE_DECIMATE}" \
      -v sfile="${sfile}" -v cfile="${cfile}" '
    function abs(x) { return x < 0 ? -x : x }
    # nearest-index lookup on the (uniform) voltage grid
    function at(target,   k) { k = int(target / dv + 0.5) + 1; if (k < 1) k = 1; if (k > n) k = n; return k }
    BEGIN {
      split(opn, a, " "); vth["n"] = a[1]; vdsat["n"] = a[2]
      split(opp, b, " "); vth["p"] = b[1]; vdsat["p"] = b[2]
      nstack = 6
      name[1] = "n_simple"; name[2] = "n_casc"; name[3] = "n_ws"
      name[4] = "p_simple"; name[5] = "p_casc"; name[6] = "p_ws"
      pol[1] = "n"; pol[2] = "n"; pol[3] = "n"
      pol[4] = "p"; pol[5] = "p"; pol[6] = "p"
    }
    # wrdata interleaves the sweep scale with every vector: v i1 v i2 ... v i6
    {
      n++
      v[n] = $1
      for (s = 1; s <= nstack; s++) cur[s, n] = $(2 * s)
    }
    END {
      if (n < 10) { print "ERROR: short sweep" > "/dev/stderr"; exit 1 }
      dv = (v[n] - v[1]) / (n - 1)

      for (s = 1; s <= nstack; s++) {
        # --- output resistance, central difference on the raw grid
        for (k = 2; k < n; k++) {
          di = cur[s, k + 1] - cur[s, k - 1]
          ro[k] = (di == 0) ? 1e15 : abs((v[k + 1] - v[k - 1]) / di)
        }
        ro[1] = ro[2]; ro[n] = ro[n - 1]

        kmid = at(0.5 * vdd)
        romid = ro[kmid]
        iout_mid = abs(cur[s, kmid])

        # Compliance is referenced to the current the stack delivers at its
        # nominal operating point (mid-rail), NOT to the extreme-Vout value:
        # a simple mirror never stops climbing with Vout, so a "99 % of the
        # value at the rail" definition would report a meaningless number.
        # Walk from mid-rail toward the rail this stack works against, and stop
        # at the first point that leaves the +/-1 % (resp. +/-5 %) band.
        isat = iout_mid
        if (pol[s] == "n") {
          vc1 = v[1]; for (k = kmid; k >= 1; k--) if (abs(abs(cur[s, k]) - isat) > 0.01 * isat) { vc1 = v[k + 1]; break }
          vc5 = v[1]; for (k = kmid; k >= 1; k--) if (abs(abs(cur[s, k]) - isat) > 0.05 * isat) { vc5 = v[k + 1]; break }
          # small-signal compliance: walk down from mid-rail to the first point
          # where ro has fallen below half its mid-rail value
          vro = v[1]; for (k = kmid; k >= 1; k--) if (ro[k] < 0.5 * romid) { vro = v[k]; break }
          hd1 = vc1; hdro = vro
        } else {
          vc1 = v[n]; for (k = kmid; k <= n; k++) if (abs(abs(cur[s, k]) - isat) > 0.01 * isat) { vc1 = v[k - 1]; break }
          vc5 = v[n]; for (k = kmid; k <= n; k++) if (abs(abs(cur[s, k]) - isat) > 0.05 * isat) { vc5 = v[k - 1]; break }
          vro = v[n]; for (k = kmid; k <= n; k++) if (ro[k] < 0.5 * romid) { vro = v[k]; break }
          hd1 = vdd - vc1; hdro = vdd - vro
        }

        printf "%s,%s,%s,%s,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.4f,%.4f,%.4f,%.4f,%.4f,%.6g,%.6g\n",
               name[s], corner, temp, vdd, iref, (pol[s] == "n" ? abs(cur[s, n]) : abs(cur[s, 1])),
               iout_mid, iout_mid / iref,
               ro[at(0.3 * vdd)], romid, ro[at(0.7 * vdd)],
               vc1, vc5, vro, hd1, hdro, vth[pol[s]], vdsat[pol[s]] >> sfile

        for (k = 1; k <= n; k += dec)
          printf "%s,%s,%s,%s,%.4f,%.6g,%.6g\n",
                 name[s], corner, temp, vdd, v[k], abs(cur[s, k]), ro[k] >> cfile
      }
    }' "${rundir}/iv.dat"
}

# --------------------------------------------------------------------------
# Entry points
# --------------------------------------------------------------------------
if [ "${1:-}" = "--one" ]; then
  shift
  run_one "$@"
  exit 0
fi

simenv_require_tools
mkdir -p "${WORK}" "${HERE}/results"

if [ "${1:-}" = "--check" ]; then
  tmpdir=$(mktemp -d)
  trap 'rm -rf "${tmpdir}"' EXIT
  run_one typical 27 3.30 "${tmpdir}/s.csv" "${tmpdir}/c.csv"
  echo "${SUMMARY_HEADER}"
  cat "${tmpdir}/s.csv"
  exit 0
fi

JOBLIST="${WORK}/jobs.txt"
: >"${JOBLIST}"
for corner in "${SIMENV_MOS_CORNERS[@]}"; do
  for temp in "${SIMENV_TEMPS[@]}"; do
    for vdd in "${SIMENV_VDDS[@]}"; do
      tag="${corner}_T${temp}_V${vdd}"
      tag="${tag//./p}"; tag="${tag//-/m}"
      echo "${corner} ${temp} ${vdd} ${WORK}/${tag}.sum ${WORK}/${tag}.cur" >>"${JOBLIST}"
    done
  done
done
NPOINTS=$(wc -l <"${JOBLIST}" | tr -d ' ')
echo "devchar-cp: ${NPOINTS} corner points x 6 stacks, $(simenv_jobs) parallel jobs"

rm -f "${WORK}"/*.sum "${WORK}"/*.cur
# shellcheck disable=SC2016
xargs -P "$(simenv_jobs)" -L 1 \
  "${BASH:-/bin/bash}" -c 'exec "$0" --one "$@"' "${HERE}/run.sh" \
  <"${JOBLIST}"

EXPECTED_ROWS=$((NPOINTS * 6))
GOT=$(cat "${WORK}"/*.sum | wc -l | tr -d ' ')
if [ "${GOT}" -ne "${EXPECTED_ROWS}" ]; then
  echo "ERROR: expected ${EXPECTED_ROWS} summary rows, collected ${GOT}" >&2
  exit 1
fi

CORNER_DESC="process{typical,ff,ss,fs,sf} x temp{-40,27,125}C x vdd{2.97,3.30,3.63}V = ${NPOINTS} points, 6 stacks each"

{
  simenv_provenance "devchar-cp" "sim/devchar-cp/tb_cp_mirror.sp" "${CORNER_DESC}"
  cat <<'EOF'
# stacks: n_simple/n_casc/n_ws (CP sink) and p_simple/p_casc/p_ws (CP source);
#   _casc = self-biased cascode, _ws = wide-swing (low-voltage) cascode
# sizing: NMOS W=5um, PMOS W=15um, L=1um, cascode-bias diode at W/4; Iref=20uA
# vcomp_i1pct/i5pct: output voltage where |Iout| first reaches 99%/95% of isat
# vcomp_ro50: output voltage where ro falls to 50% of its mid-rail value
# headroom_*: same boundary as distance from the stack's own rail
#   (ground for n_*, Vdd for p_*)
# vth_ref/vdsat_ref: operating point of the polarity's reference mirror device
EOF
  echo "${SUMMARY_HEADER}"
  cat "${WORK}"/*.sum | sort -t, -k1,1 -k2,2 -k3,3n -k4,4n
} >"${OUT_SUMMARY}"

{
  simenv_provenance "devchar-cp (full output I-V curves)" \
    "sim/devchar-cp/tb_cp_mirror.sp" "${CORNER_DESC}"
  cat <<'EOF'
# Complete output characteristic of every stack at every corner, decimated from
# the 10 mV simulation grid to 50 mV. ro is a central difference on the raw
# 10 mV grid, so the knee is resolved at full simulation resolution.
EOF
  echo "${CURVES_HEADER}"
  cat "${WORK}"/*.cur | sort -t, -k1,1 -k2,2 -k3,3n -k4,4n -k5,5n
} >"${OUT_CURVES}"

echo "devchar-cp: wrote ${OUT_SUMMARY} and ${OUT_CURVES}"
