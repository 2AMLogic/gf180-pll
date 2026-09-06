#!/usr/bin/env bash
# gf180-pll :: period-jitter-band-top :: verify tb.json's configuration bits
# against sim/lib/pll_top_dut.sh, the single owner of that encoding.
#
# WHY THIS EXISTS.  sim/lib/pll_top_dut.sh owns what `pll_top`'s 22 static
# configuration bits MEAN.  `divider_chain.sch`'s one-hot SEL / binary P
# encoding is easy to get subtly wrong in a way that still locks, at the wrong
# N -- and a period-jitter number taken at the wrong N is not wrong-looking,
# it is just wrong.  A JSON manifest cannot call a bash function, so the codes
# are written into tb.json and this script asserts they are EXACTLY what the
# helper produces.
#
# This campaign checks one thing sim/reference-spur's equivalent does not: its
# VCO band code is NOT fixed.  spec/pll.md's band-selection rule puts 34 of
# the 45 PVT points in band 6 and 11 in band 7 at 200 MHz, so the band bits
# live per point on the manifest's `op` sweep axis.  Every one of those points
# is checked here against `cloop_band_params` for the band its own point id
# names -- an id that says `b7` while carrying band 6's bits would otherwise
# read correctly and simulate wrongly.
#
#   ./check_config.sh      # prints each field and a PASS/FAIL verdict
#
# Exit 0 if every bit matches, 1 otherwise.  What this does NOT check is
# whether the per-corner band assignment is the one the ratified rule
# selects -- that is band_and_vstart_from_vco_record.py --check's job, and
# sim/tests/test_period_jitter_band_top_grid.py runs it in CI.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${HERE}/../../.." && pwd)"
TB="${HERE}/tb.json"

# shellcheck source=/dev/null
. "${ROOT}/sim/lib/pll_top_dut.sh"

# The operating point tb.json declares, read back out of the manifest itself so
# this check cannot drift from it.
N="$(python3 -c 'import json,sys; print(int(float(json.load(open(sys.argv[1]))["params"]["nratio"])))' "${TB}")"
TRIM=0

fail=0

echo "period-jitter-band-top config check -- N=${N}, Icp trim code=${TRIM}, band per point"
echo "divider (cloop_divider_params ${N}):"
cloop_check_codes "${TB}" "$(cloop_divider_params "${N}")"
echo "Icp trim (cloop_trim_params ${TRIM}):"
cloop_check_codes "${TB}" "$(cloop_trim_params "${TRIM}")"

# No fixed band bits may sit in `params`: they would be emitted BEFORE the
# axis point's own and so would not change the deck, but the manifest would
# read as though the band were static -- the exact misreading this campaign
# exists to avoid.
echo "band bits are per point, not fixed in params:"
for bit in b0_code b1_code b2_code; do
  if python3 -c 'import json,sys; sys.exit(0 if sys.argv[2] in json.load(open(sys.argv[1]))["params"] else 1)' "${TB}" "${bit}"; then
    printf '  FAIL %-12s is fixed in tb.json params; it belongs on the op axis\n' "${bit}"
    fail=1
  else
    printf '  ok   %-12s absent from params\n' "${bit}"
  fi
done

# Every `op` axis point: the band bits it carries must be cloop_band_params'
# output for the band its own id names.
echo "VCO band bits, per op-axis point (cloop_band_params <band from the point id>):"
while read -r pid band b0 b1 b2; do
  want="$(cloop_band_params "${band}")"
  got="b0_code=${b0} b1_code=${b1} b2_code=${b2}"
  if [ "${got}" != "${want}" ]; then
    printf '  FAIL %-14s band %s: tb.json=%s  pll_top_dut.sh=%s\n' "${pid}" "${band}" "${got}" "${want}"
    fail=1
  else
    printf '  ok   %-14s band %s: %s\n' "${pid}" "${band}" "${got}"
  fi
done < <(python3 - "${TB}" <<'PY'
import json, re, sys
points = json.load(open(sys.argv[1]))["sweeps"]["op"]["points"]
for pid, spec in sorted(points.items()):
    m = re.match(r"^b(\d)vs", pid)
    if m is None:
        print("%s ?? ? ? ?" % pid)
        continue
    p = spec["params"]
    print(pid, m.group(1), p["b0_code"], p["b1_code"], p["b2_code"])
PY
)

# The DUT instance line in the fragment must be `cloop_instance`'s output
# verbatim, folded onto continuation lines: same ports, same ORDER, since the
# instance line is positional and a swapped pair simulates happily.
echo "DUT instance line (cloop_instance xdut):"
cloop_check_instance_line "${HERE}/tb_period_jitter_band_top.sp" xdut

if [ "${fail}" -eq 0 ]; then
  echo "PASS -- tb.json's configuration bits are sim/lib/pll_top_dut.sh's own encoding"
else
  echo "FAIL -- fix tb.json (or the deck) to match sim/lib/pll_top_dut.sh" >&2
fi
exit "${fail}"
