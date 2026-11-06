#!/usr/bin/env bash
# gf180-pll :: the pll_top closed-loop DUT assembly path.
#
# NAMING NOTE, and the reconciliation it went through.  This file is #52's
# `sim/lib/assemble_closed_loop.sh`, renamed.  That path was already taken on
# `main` by a DIFFERENT helper (landed by #12/PR #56) which assembled a
# closed-loop deck by concatenating the five block exports rather than by
# instantiating `design/pll_top.sch`, and which #12's `sim/lock-time` and
# `sim/output-range` runners called as an executable.  Overwriting it here
# would have broken already-recorded evidence, so the two coexisted under
# different names until #159 reconciled them.  Evidence records and testbench
# comments minted before this file's rename still refer to it by its old
# path; the file is the same file.
#
# WHO USES IT.  All four closed-loop campaigns build their decks through this
# file: sim/pll-top-smoke (#52), sim/supply-sensitivity (#14), and --
# since #159 -- #12's sim/lock-time and sim/output-range.  #159 also re-took
# #12's committed EVIDENCE against this DUT (a full-grid mint per campaign:
# sim/lock-time/records/20260831-052456-effc505.md,
# sim/output-range/records/20260819-160843-4e32f91.md) and then deleted
# `sim/lib/assemble_closed_loop.sh`, which had no live caller left and was
# retained only as long as it was the cited provenance of not-yet-superseded
# evidence.  Records dated before that migration still name it in their own
# Netlist provenance field -- those records are append-only and are not
# restated here.  #13 (period-jitter) and #49 are unwritten and should start
# here.
#
# `design/pll_top.sch` is now the single owner of the top-level wiring, and
# this file the single owner of "how a testbench gets hold of it," for every
# closed-loop campaign in the tree.
#
# Usage from a campaign runner (after sourcing sim/lib/simenv.sh):
#
#   . "$(dirname "$0")/../../lib/simenv.sh"
#   . "$(dirname "$0")/../../lib/pll_top_dut.sh"
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
#   3. WHAT the configuration bits mean.  `pll_top` has 26 static inputs, and
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
# transcribed: a 36-port instance line typed by hand in four campaigns is four
# chances to swap two nets and still get a deck that simulates.
CLOOP_SUBCKT="pll_top"
CLOOP_PORTS=(
  REF B0 B1 B2 CPB0 CPB1
  LDT0 LDT1 LDT2 LDT3
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
    # This file's own path, current as of #159.  Snapshots frozen before then
    # carry the pre-rename name (see the NAMING NOTE above); they are
    # append-only evidence and are not rewritten to match.
    echo "* ASSEMBLED by sim/lib/pll_top_dut.sh -- do not edit."
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

# cloop_window_trim_params <window-trim code 0..15>
#
# Prints `ldt0_code=.. ldt1_code=.. ldt2_code=.. ldt3_code=..` for the lock
# detector's 4-bit window trim (delaywin_3v3: each stage carries an always-on
# MOS-cap load plus four binary-weighted switched segments, so raising the code
# widens the window monotonically -- DR-014, #411).
#
# This is a PROCESS trim, set once at test from a measurement of the cell's own
# delay at a fixed reference condition, and held for the life of the part.  It
# is not a runtime knob and nothing on-chip writes it (DR-002 Decision 4's
# no-calibration-FSM boundary).  WHICH code a corner needs is answered by
# sim/lock-window-trim, not by this file, exactly as WHICH band a frequency
# needs is answered by sim/vco-tuning-range -- a campaign picks the code and
# says in its record where it got it.
#
# ${CLOOP_WINDOW_TRIM_NOMINAL} is the centre code, and is what a campaign that
# is not itself about the lock window should pass: it is the middle of the
# range, so neither the fast nor the slow end of the process distribution is
# silently favoured.
CLOOP_WINDOW_TRIM_NOMINAL=8

cloop_window_trim_params() {
  local c="$1"
  case "${c}" in
    ''|*[!0-9]*) echo "ERROR: cloop_window_trim_params: code='${c}' is not an integer" >&2; exit 2 ;;
  esac
  [ "${c}" -ge 0 ] && [ "${c}" -le 15 ] || {
    echo "ERROR: cloop_window_trim_params: window trim code ${c} outside the 4-bit range 0..15" >&2; exit 2; }
  printf 'ldt0_code=%d ldt1_code=%d ldt2_code=%d ldt3_code=%d\n' \
    $((c & 1)) $(((c >> 1) & 1)) $(((c >> 2) & 1)) $(((c >> 3) & 1))
}

# ---------------------------------------------------- tb.json verification --
#
# Shared by every closed-loop campaign's check_config.sh: asserting that a
# tb.json manifest's static configuration params, and a testbench fragment's
# DUT instance line, are exactly what this file's own encoding produces.
# Originally duplicated byte-for-byte between sim/reference-spur and
# sim/period-jitter-band-top (#276); consolidated here so both campaigns
# check against one copy of this logic rather than two.
#
# Every function below sets the caller's `fail` variable to 1 on mismatch and
# leaves it alone on a match -- callers declare `fail=0` before the first call
# and `exit "${fail}"` after the last, same as before extraction.

# cloop_check_field <tb.json> <field> <want>
#
# Asserts tb.json's params[<field>] equals <want> (a value already produced by
# one of the cloop_*_params functions above), printing a PASS/FAIL line either
# way.
cloop_check_field() {
  local tb="$1" field="$2" want="$3" got
  got="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["params"][sys.argv[2]])' "${tb}" "${field}")"
  if [ "${got}" != "${want}" ]; then
    printf '  FAIL %-12s tb.json=%s  pll_top_dut.sh=%s\n' "${field}" "${got}" "${want}"
    # shellcheck disable=SC2034 # read by the sourcing check_config.sh, not this file
    fail=1
  else
    printf '  ok   %-12s %s\n' "${field}" "${got}"
  fi
}

# cloop_check_codes <tb.json> "<field=value field=value ...>"
#
# Runs cloop_check_field over each `field=value` pair in a cloop_*_params
# line, e.g. cloop_check_codes "${TB}" "$(cloop_divider_params "${N}")".
cloop_check_codes() {
  local tb="$1" kv
  for kv in $2; do
    cloop_check_field "${tb}" "${kv%%=*}" "${kv#*=}"
  done
}

# cloop_check_instance_line <fragment.sp> [<instance-name>]
#
# Asserts the DUT instance line in a testbench fragment (folded onto its `+`
# continuation lines) is byte-for-byte cloop_instance's output: same ports,
# same ORDER, since the instance line is positional and a swapped pair
# simulates happily without erroring.
cloop_check_instance_line() {
  local frag="$1" inst="${2:-xdut}"
  local want_inst got_inst
  want_inst="$(cloop_instance "${inst}" | tr -s ' ')"
  got_inst="$(awk -v inst="${inst}" '
      $0 ~ "^" inst " " { line = $0; f = 1; next }
      f && /^\+/         { sub(/^\+ */, " "); line = line $0; next }
      f                  { exit }
      END                { print line }
    ' "${frag}" | tr -s ' ' | sed -e 's/ *$//')"
  if [ "${got_inst}" != "${want_inst}" ]; then
    echo "  FAIL instance line does not match cloop_instance's output"
    echo "    deck:   ${got_inst}"
    echo "    helper: ${want_inst}"
    # shellcheck disable=SC2034 # read by the sourcing check_config.sh, not this file
    fail=1
  else
    echo "  ok   ${#CLOOP_PORTS[@]}-port instance line matches"
  fi
}

# cloop_check_band_top_config <tb.json> <deck.sp>
#
# The whole check_config.sh body shared by the band-top campaigns, whose VCO
# band code is per point (on the manifest's `op` axis) rather than fixed.  Reads
# N from tb.json, then asserts: the divider / Icp-trim / window-trim codes are
# the helpers' own output; no b*_code sits in `params`; every `op` point's band
# bits are cloop_band_params' output for the band its id (`b<digit>vs...`)
# names; and the deck's DUT instance line is cloop_instance's output.  The
# campaign name in the banner is the campaign directory's name.  Returns 0 if
# every bit matches, 1 otherwise.
cloop_check_band_top_config() {
  local tb="$1" deck="$2" campaign N trim=0 wintrim bit pid band b0 b1 b2 want got
  campaign="$(basename "$(dirname "$(cd "$(dirname "${tb}")" && pwd)")")"
  # The operating point tb.json declares, read back out of the manifest itself
  # so this check cannot drift from it.
  N="$(python3 -c 'import json,sys; print(int(float(json.load(open(sys.argv[1]))["params"]["nratio"])))' "${tb}")"
  # The lock detector's 4-bit window trim (DR-014, #411): the CENTRE code.
  # These campaigns are not about the lock window, so they run the cell at the
  # middle of its range; sim/lock-window-trim owns the per-part code.
  wintrim=${CLOOP_WINDOW_TRIM_NOMINAL:-8}

  fail=0

  echo "${campaign} config check -- N=${N}, Icp trim code=${trim}, band per point"
  echo "divider (cloop_divider_params ${N}):"
  cloop_check_codes "${tb}" "$(cloop_divider_params "${N}")"
  echo "Icp trim (cloop_trim_params ${trim}):"
  cloop_check_codes "${tb}" "$(cloop_trim_params "${trim}")"
  echo "window trim (cloop_window_trim_params ${wintrim}):"
  cloop_check_codes "${tb}" "$(cloop_window_trim_params "${wintrim}")"

  # No fixed band bits may sit in `params`: they would be emitted BEFORE the
  # axis point's own and so would not change the deck, but the manifest would
  # read as though the band were static.
  echo "band bits are per point, not fixed in params:"
  for bit in b0_code b1_code b2_code; do
    if python3 -c 'import json,sys; sys.exit(0 if sys.argv[2] in json.load(open(sys.argv[1]))["params"] else 1)' "${tb}" "${bit}"; then
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
  done < <(python3 - "${tb}" <<'PY'
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
  # verbatim, folded onto continuation lines: same ports, same ORDER.
  echo "DUT instance line (cloop_instance xdut):"
  cloop_check_instance_line "${deck}" xdut

  if [ "${fail}" -eq 0 ]; then
    echo "PASS -- tb.json's configuration bits are sim/lib/pll_top_dut.sh's own encoding"
  else
    echo "FAIL -- fix tb.json (or the deck) to match sim/lib/pll_top_dut.sh" >&2
  fi
  return "${fail}"
}
