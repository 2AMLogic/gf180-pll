#!/usr/bin/env bash
# gf180-pll :: reference-spur :: verify tb.json's configuration bits against
# sim/lib/pll_top_dut.sh, the single owner of that encoding.
#
# WHY THIS EXISTS.  sim/lib/pll_top_dut.sh owns three things a closed-loop
# campaign must not re-derive by hand: where the DUT netlist comes from, how
# the deck is assembled, and what the 22 static configuration bits MEAN.  The
# third is the dangerous one -- `divider_chain.sch`'s one-hot SEL / binary P
# encoding is easy to get subtly wrong in a way that still locks, at the wrong
# N (that helper's own header says so).
#
# A `sim/harness` campaign gets the first two for free and better: tb.json's
# `dut` key composes the same committed `design/netlist/pll_top.spice`, and the
# harness freezes a self-contained snapshot per record.  What it cannot do is
# call a bash function for the bit codes, because a JSON manifest is data.  So
# the codes are written into tb.json -- and this script asserts they are
# EXACTLY what the helper produces, rather than leaving a reader to trust that
# they look plausible.  Run it whenever the operating point changes.
#
#   ./check_config.sh      # prints each field and a PASS/FAIL verdict
#
# Exit 0 if every bit matches, 1 otherwise.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${HERE}/../../.." && pwd)"
TB="${HERE}/tb.json"

# shellcheck source=/dev/null
. "${ROOT}/sim/lib/pll_top_dut.sh"

# The operating point tb.json declares, read back out of the manifest itself so
# this check cannot drift from it.
N="$(python3 -c 'import json,sys; print(int(float(json.load(open(sys.argv[1]))["params"]["nratio"])))' "${TB}")"
BAND=6
TRIM=0

fail=0

check_field() {
  local field="$1" want="$2" got
  got="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["params"][sys.argv[2]])' "${TB}" "${field}")"
  if [ "${got}" != "${want}" ]; then
    printf '  FAIL %-12s tb.json=%s  pll_top_dut.sh=%s\n' "${field}" "${got}" "${want}"
    fail=1
  else
    printf '  ok   %-12s %s\n' "${field}" "${got}"
  fi
}

check_codes() {
  local kv
  for kv in $1; do
    check_field "${kv%%=*}" "${kv#*=}"
  done
}

echo "reference-spur config check -- N=${N}, band=${BAND}, Icp trim code=${TRIM}"
echo "divider (cloop_divider_params ${N}):"
check_codes "$(cloop_divider_params "${N}")"
echo "VCO band (cloop_band_params ${BAND}):"
check_codes "$(cloop_band_params "${BAND}")"
echo "Icp trim (cloop_trim_params ${TRIM}):"
check_codes "$(cloop_trim_params "${TRIM}")"

# The DUT instance line in the fragment must be `cloop_instance`'s output
# verbatim, folded onto continuation lines: same ports, same ORDER, since the
# instance line is positional and a swapped pair simulates happily.
echo "DUT instance line (cloop_instance xdut):"
want_inst="$(cloop_instance xdut | tr -s ' ')"
got_inst="$(awk '
    /^xdut /   { line = $0; f = 1; next }
    f && /^\+/ { sub(/^\+ */, " "); line = line $0; next }
    f          { exit }
    END        { print line }
  ' "${HERE}/tb_ref_spur.sp" | tr -s ' ' | sed -e 's/ *$//')"
if [ "${got_inst}" != "${want_inst}" ]; then
  echo "  FAIL instance line does not match cloop_instance's output"
  echo "    deck:   ${got_inst}"
  echo "    helper: ${want_inst}"
  fail=1
else
  echo "  ok   32-port instance line matches"
fi

if [ "${fail}" -eq 0 ]; then
  echo "PASS -- tb.json's configuration bits are sim/lib/pll_top_dut.sh's own encoding"
else
  echo "FAIL -- fix tb.json (or the deck) to match sim/lib/pll_top_dut.sh" >&2
fi
exit "${fail}"
