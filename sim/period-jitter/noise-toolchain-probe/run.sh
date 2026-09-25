#!/usr/bin/env bash
#
# Re-derive the four toolchain facts DR-023 turns on.
#
# This is NOT a verification campaign and mints no evidence record: it measures
# the SIMULATOR, not the design. No number it produces describes this PLL, and
# none appears in spec/pll.md as a design result. It exists so that DR-023's
# claims about what ngspice can and cannot do are reproducible by a reader
# instead of asserted, which is the same standard sim/ holds design claims to.
#
# It is cheap and single-corner by construction -- four sub-second runs plus a
# seven-point bias sweep, all `typical`/27 C. A corner sweep would be
# meaningless here: whether a simulator command exists does not depend on PVT.
#
# Usage:  sim/period-jitter/noise-toolchain-probe/run.sh [-o OUTDIR]
# Output: OUTDIR/*.log (default: this script's own logs/), plus a summary table
#         on stdout. Exits non-zero if a probe's log could not be produced.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${HERE}/../../.." && pwd)"
OUTDIR="${HERE}/logs"

while [ $# -gt 0 ]; do
  case "$1" in
    -o|--outdir) OUTDIR="$2"; shift 2 ;;
    -h|--help)   sed -n '2,20p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

command -v ngspice >/dev/null 2>&1 || {
  echo "FAIL: ngspice is not on PATH" >&2; exit 1; }

# Resolve the PDK exactly as every other campaign here does, so this probe can
# never drift onto a different model set than the records it is cited beside.
eval "$(python3 "${REPO_ROOT}/sim/run_corners.py" --print-env)"
DESIGN_NGSPICE="${GF180_MODELS}/design.ngspice"
MODELS_NGSPICE="${GF180_MODELS}/sm141064.ngspice"
for f in "${DESIGN_NGSPICE}" "${MODELS_NGSPICE}"; do
  [ -r "$f" ] || { echo "FAIL: PDK model file not readable: $f" >&2; exit 1; }
done

mkdir -p "${OUTDIR}"
WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

subst() {  # subst <in> <out> [VGS]
  sed -e "s#@DESIGN_NGSPICE@#${DESIGN_NGSPICE}#g" \
      -e "s#@MODELS_NGSPICE@#${MODELS_NGSPICE}#g" \
      -e "s#@VGS@#${3:-}#g" "$1" > "$2"
}

echo "ngspice: $(ngspice -v 2>&1 | sed -n '2p' | tr -s ' ')"
echo "PDK:     ${GF180_MODELS}"
echo

# --------------------------------------------------------------------------
# Probes 1, 2 and 4 need no PDK; probe 3 does. All four are run the same way.
# --------------------------------------------------------------------------
for probe in trannoise trnoise device_noise pss; do
  subst "${HERE}/probe_${probe}.sp" "${WORK}/${probe}.sp"
  # `pss` is EXPECTED to fail -- an absent command is this probe's whole
  # finding -- so no probe's exit status is treated as the result. The log is.
  ngspice -b "${WORK}/${probe}.sp" > "${OUTDIR}/${probe}.log" 2>&1 || true
  [ -s "${OUTDIR}/${probe}.log" ] || {
    echo "FAIL: probe ${probe} produced no log" >&2; exit 1; }
done

# --------------------------------------------------------------------------
# Probe 3b: the bias sweep. One process per point -- see the template's header
# for why a .control foreach loop is wrong here.
# --------------------------------------------------------------------------
: > "${OUTDIR}/sid_bias.log"
for vgs in 0.30 0.60 0.90 1.20 1.65 2.40 3.30; do
  subst "${HERE}/probe_sid_bias.sp.in" "${WORK}/sid_${vgs}.sp" "${vgs}"
  {
    echo "===== VGS ${vgs} ====="
    ngspice -b "${WORK}/sid_${vgs}.sp" 2>&1 || true
  } >> "${OUTDIR}/sid_bias.log"
done

# --------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------
echo "--- probe 1: .option TRANNOISE=1 (transient device-noise injection) ---"
grep -E '^(vmin|vmax|vspan)' "${OUTDIR}/trannoise.log" || true
echo
echo "--- probe 2: trnoise() explicit PWL noise source ---"
grep -E '^(vmin|vmax|vrms)' "${OUTDIR}/trnoise.log" || true
echo
echo "--- probe 3: .noise per-device per-mechanism decomposition ---"
grep -cE '^ *(o|i)noise_total\.m\.xm1\.m0\.' "${OUTDIR}/device_noise.log" \
  | sed 's/^/  per-device noise vectors produced: /'
grep -E '^onoise_total' "${OUTDIR}/device_noise.log" || true
echo
echo "--- probe 4: pss (periodic steady state) ---"
grep -E 'no such command|Sorry, no help' "${OUTDIR}/pss.log" || \
  echo "  NOTE: pss did NOT report as absent -- DR-023 Decision 2 needs revisiting"
echo
echo "--- probe 3b: ring stage nfet noise generators vs. gate bias ---"
python3 - "${OUTDIR}/sid_bias.log" <<'PY'
import re, sys

text = open(sys.argv[1]).read()
blocks = re.split(r'^===== VGS ([\d.]+) =====$', text, flags=re.M)[1:]

def grab(block, key):
    m = re.search(rf'^{re.escape(key)}\s*=\s*(\S+)', block, flags=re.M)
    return float(m.group(1)) if m else float('nan')

print(f"{'Vgs(V)':>7} {'Id(A)':>13} {'thermal(V/rtHz)':>17} {'flicker(V/rtHz)':>17}")
rows = []
for vgs, block in zip(blocks[0::2], blocks[1::2]):
    # The units check: the 1 ohm sense resistor must read sqrt(4kT*R*1Hz).
    rs = grab(block, 'onoise_total_rs_thermal')
    expect = (4 * 1.380649e-23 * 300.15 * 1.0) ** 0.5
    if abs(rs - expect) / expect > 0.01:
        sys.exit(f"FAIL: units check -- rs thermal {rs:.6e} vs expected {expect:.6e}")
    idd = grab(block, '-i(vd)')
    th  = grab(block, 'onoise_total.m.xm1.m0.id')
    fl  = grab(block, 'onoise_total.m.xm1.m0.1overf')
    rows.append((float(vgs), idd, th, fl))
    print(f"{vgs:>7} {idd:13.6e} {th:17.6e} {fl:17.6e}")

th = [r[2] for r in rows]; fl = [r[3] for r in rows]
import math
print()
print(f"  units check PASSED (1 ohm sense resistor reads sqrt(4kTR*1Hz) to <1%)")
print(f"  channel-thermal PSD span over the swept V_gs: "
      f"{(max(th)/min(th))**2:.3e}x  ({20*math.log10(max(th)/min(th)):.1f} dB)")
print(f"  flicker PSD span over the swept V_gs:         "
      f"{(max(fl)/min(fl))**2:.3e}x  ({20*math.log10(max(fl)/min(fl)):.1f} dB)")
PY
