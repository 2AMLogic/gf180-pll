#!/usr/bin/env bash
# gf180-pll :: the ONE closed-loop DUT assembly path.
#
# Every campaign that simulates the whole PLL -- #12 (lock-time,
# output-range), #13 (period-jitter), #14 (supply-sensitivity), #49 -- builds
# its deck through this file instead of assembling a top level of its own.
# That is the entire point of #52: `design/pll_top.sch` is the single owner of
# the top-level wiring, and this is the single owner of "how a testbench gets
# hold of it".
#
# Usage from a campaign runner (after sourcing sim/lib/simenv.sh):
#
#   . "$(dirname "$0")/../../lib/simenv.sh"
#   . "$(dirname "$0")/../../lib/assemble_closed_loop.sh"
#
#   cloop_require_netlist                      # committed export must exist
#   cloop_assemble "${HERE}/tb_foo.sp" "${WORK}/dut_foo.sp"
#   simenv_run_deck "${WORK}/dut_foo.sp" "${WORK}" "${tag}" "${libs}" "${temp}" \
#       vsup=3.30 $(cloop_divider_params 8) $(cloop_band_params 2) ...
#
# Three things it owns, each of which is a place where two campaigns would
# otherwise drift apart:
#
#   1. WHERE the DUT comes from.  `design/netlist/pll_top.spice`, the committed
#      export of `design/pll_top.sch`.  Not a per-campaign xschem invocation,
#      not a hand-transcribed copy.
#   2. HOW the deck is put together.  The exported subcircuit is prepended to
#      the campaign's stimulus fragment into one file, so the frozen
#      `netlist-snapshots/<record-id>.spice` a record cites is self-contained
#      and reproduces the run from the record alone.  Same shape as the
#      existing per-block campaigns (sim/divider-ratio, sim/lock-detector).
#   3. WHAT the configuration bits mean.  `pll_top` has 22 static inputs, and
#      the divider's one-hot SEL / binary P encoding is easy to get subtly
#      wrong in a way that still locks -- at the wrong N.  Encoding it once,
#      here, from divider_chain.sch's own documented rule, means a campaign
#      asks for "N = 8" rather than for twelve individual bits.
#
# shellcheck shell=bash

set -euo pipefail

CLOOP_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLOOP_ROOT="$(cd "${CLOOP_LIB_DIR}/../.." && pwd)"

# The committed export of design/pll_top.sch.  `design/netlist.sh --check`
# is what keeps it honest against the schematic; this file never regenerates
# it, so a record always freezes what is committed rather than whatever the
# working tree happened to netlist to.
CLOOP_NETLIST="${CLOOP_ROOT}/design/netlist/pll_top.spice"

# The name of the exported subcircuit, and its port list in netlist order.
# Kept here so a testbench's instance line is generated rather than
# transcribed: a 32-port instance line typed by hand in four campaigns is four
# chances to swap two nets and still get a deck that simulates.
CLOOP_SUBCKT="pll_top"
CLOOP_PORTS=(
  REF B0 B1 B2 CPB0 CPB1
  P0 P1 P2 P3 P4 P5
  SEL0 SEL1 SEL2 SEL3 SEL4 SEL5
  IBN ICN IBP ICP
  CLK DIVOUT FB LOCK
  VCTRL VDD VDD_VCO GND_VCO VDD_DIV VSS
)

# --------------------------------------------------------------- preflight --

cloop_require_netlist() {
  [ -f "${CLOOP_NETLIST}" ] || {
    echo "ERROR: ${CLOOP_NETLIST} missing -- run design/netlist.sh" >&2
    exit 1
  }
  # A port list that wrapped onto a commented `*+` line would silently demote
  # the last few ports to internal nodes; design/netlist.sh's check_export
  # rejects that at export time, and this is the cheap read-side restatement so
  # a stale committed file minted before that check cannot slip through.
  if grep -qE '^\*\+' "${CLOOP_NETLIST}"; then
    echo "ERROR: ${CLOOP_NETLIST} contains a commented '*+' continuation --" >&2
    echo "       its .subckt port list is truncated.  Re-run design/netlist.sh." >&2
    exit 1
  fi
  # The declared port list, with any `+` continuation folded back onto one
  # line, must be exactly CLOOP_PORTS -- same names, same ORDER, since the
  # instance line below is positional.
  local declared want
  declared="$(awk '
      /^\.subckt +pll_top( |$)/ { sub(/^\.subckt +pll_top */, ""); printf "%s ", $0; f = 1; next }
      f && /^\+/                { sub(/^\+ */, "");                printf "%s ", $0;        next }
      f                         { exit }
    ' "${CLOOP_NETLIST}" | tr -s ' ' | sed -e 's/^ *//' -e 's/ *$//')"
  want="${CLOOP_PORTS[*]}"
  if [ "${declared}" != "${want}" ]; then
    echo "ERROR: ${CLOOP_NETLIST} port list does not match this file's CLOOP_PORTS." >&2
    echo "  netlist: ${declared}" >&2
    echo "  library: ${want}" >&2
    echo "       design/pll_top.sch's pin list changed; update CLOOP_PORTS (and" >&2
    echo "       every testbench's net names) rather than letting them drift." >&2
    exit 1
  fi
}

# --------------------------------------------------------------- assembly --

# cloop_assemble <tb-fragment> <out-deck>
#
# Writes "<committed pll_top export> + <campaign stimulus>" to <out-deck>, and
# only touches the file when the bytes actually change, so an unchanged DUT
# keeps its mtime and a runner's resume cache survives a restart (the same
# reason the per-block runners do it that way).
cloop_assemble() {
  local frag="$1" out="$2"
  cloop_require_netlist
  [ -f "${frag}" ] || { echo "ERROR: testbench fragment ${frag} not found" >&2; exit 1; }
  mkdir -p "$(dirname "${out}")"
  local tmp="${out}.$$.new"
  {
    echo "* ASSEMBLED by sim/lib/assemble_closed_loop.sh -- do not edit."
    echo "* DUT: design/netlist/pll_top.spice (export of design/pll_top.sch, #52)"
    echo "* Stimulus: ${frag#"${CLOOP_ROOT}/"}"
    cat "${CLOOP_NETLIST}"
    cat "${frag}"
  } >"${tmp}"
  if cmp -s "${tmp}" "${out}"; then rm -f "${tmp}"; else mv "${tmp}" "${out}"; fi
}

# cloop_instance [<instance-name>]
#
# Prints the SPICE instance line for one pll_top, using each port's own name
# lowercased as the net name.  A testbench that uses this line refers to the
# DUT's pins by those net names (ref, clk, fb, lock, vctrl, vdd, ...) and never
# has to know the port ORDER.
cloop_instance() {
  local inst="${1:-xdut}"
  local nets="" p
  for p in "${CLOOP_PORTS[@]}"; do
    nets="${nets} $(printf '%s' "${p}" | tr '[:upper:]' '[:lower:]')"
  done
  printf '%s%s %s\n' "${inst}" "${nets}" "${CLOOP_SUBCKT}"
}

# ------------------------------------------------------- configuration bits --

# cloop_divider_params <N>
#
# Prints `sel0_code=..  ... p5_code=..` for a target divide ratio N, in the
# encoding divider_chain.sch documents:
#
#     N = 2^k + sum_{j<k} P_j * 2^j ,  with the one-hot SEL_(k-1) = 1
#
# i.e. k = floor(log2 N) active cells, and the residual N - 2^k written into
# the low k modulus bits.  Bits at or above k do not participate (their cells
# are past the chain termination) and are emitted as 0 so the deck is
# deterministic rather than floating.
#
# DR-001 Decision 3 ratifies N = 4..64; 2..3 and 65..127 exist for free in the
# six-cell chain and are explicitly NOT a spec claim, so they are refused here
# rather than quietly allowed into an evidence record.
cloop_divider_params() {
  local n="$1"
  case "${n}" in
    ''|*[!0-9]*) echo "ERROR: cloop_divider_params: N='${n}' is not an integer" >&2; exit 2 ;;
  esac
  if [ "${n}" -lt 4 ] || [ "${n}" -gt 64 ]; then
    echo "ERROR: cloop_divider_params: N=${n} is outside the ratified 4..64 range" >&2
    echo "       (DR-001 Decision 3).  N<4 and N>64 are reachable but are not a" >&2
    echo "       spec claim; putting one in an evidence record needs a decision" >&2
    echo "       record first." >&2
    exit 2
  fi
  local k=0 pow=1
  while [ $((pow * 2)) -le "${n}" ]; do pow=$((pow * 2)); k=$((k + 1)); done
  local resid=$((n - pow)) j out=""
  for j in 0 1 2 3 4 5; do
    if [ "${j}" -eq $((k - 1)) ]; then out="${out} sel${j}_code=1"; else out="${out} sel${j}_code=0"; fi
  done
  for j in 0 1 2 3 4 5; do
    if [ "${j}" -lt "${k}" ] && [ $(( (resid >> j) & 1 )) -eq 1 ]; then
      out="${out} p${j}_code=1"
    else
      out="${out} p${j}_code=0"
    fi
  done
  printf '%s\n' "${out# }"
}

# cloop_band_params <band-code 0..7>
#
# Prints `b0_code=.. b1_code=.. b2_code=..` for the VCO's 3-bit coarse band
# select (vco.sch: I_stage proportional to 1.65^code, code = B2*4 + B1*2 + B0).
# WHICH band a given target frequency needs is a per-corner question answered
# by sim/vco-tuning-range, not by this file -- a campaign picks the code and
# says in its record where it got it.
cloop_band_params() {
  local c="$1"
  case "${c}" in
    ''|*[!0-9]*) echo "ERROR: cloop_band_params: band='${c}' is not an integer" >&2; exit 2 ;;
  esac
  [ "${c}" -ge 0 ] && [ "${c}" -le 7 ] || {
    echo "ERROR: cloop_band_params: band ${c} outside the 3-bit range 0..7" >&2; exit 2; }
  printf 'b0_code=%d b1_code=%d b2_code=%d\n' \
    $((c & 1)) $(((c >> 1) & 1)) $(((c >> 2) & 1))
}

# cloop_trim_params <icp-code 0..3>
#
# Prints `cpb0_code=.. cpb1_code=..` for the charge pump's 2-bit unit-element
# Icp trim (cp.sch: Icp = Iunit * (1 + B0 + 2*B1)).  Code 2 is the nominal
# setting design/README.md characterises the block at.
cloop_trim_params() {
  local c="$1"
  case "${c}" in
    ''|*[!0-9]*) echo "ERROR: cloop_trim_params: code='${c}' is not an integer" >&2; exit 2 ;;
  esac
  [ "${c}" -ge 0 ] && [ "${c}" -le 3 ] || {
    echo "ERROR: cloop_trim_params: Icp code ${c} outside the 2-bit range 0..3" >&2; exit 2; }
  printf 'cpb0_code=%d cpb1_code=%d\n' $((c & 1)) $(((c >> 1) & 1))
}
