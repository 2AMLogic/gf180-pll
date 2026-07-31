#!/usr/bin/env bash
# gf180-pll :: regenerate design/netlist/vco.spice from the xschem schematics.
#
# xschem netlists the top-level schematic with its own .subckt/.ends lines
# commented out (`**.subckt vco ...`), because a top-level sheet is normally a
# testbench. This block IS a subcircuit, so the two comment markers are
# uncommented here. That is the whole post-processing step: no other line of the
# xschem output is altered, so the committed netlist stays a faithful export of
# design/vco.sch.
#
# Usage:
#   ./design/netlist.sh          # regenerate design/netlist/vco.spice
#   ./design/netlist.sh --check  # regenerate into a temp dir and diff (CI-safe)

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${HERE}/netlist/vco.spice"
TOP="${HERE}/vco.sch"

command -v xschem >/dev/null 2>&1 || {
  echo "ERROR: xschem not found on PATH" >&2
  exit 1
}

TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT

# -n netlist, -s spice format, -q quit when done, -x no GUI.
# xschem 3.4.7 exits 10 on a successful `-q` batch netlist, so the exit status
# is deliberately ignored; the netlist file's existence is the success check.
xschem -n -s -q -x --rcfile "${HERE}/xschemrc" \
  --netlist_path "${TMP}" "${TOP}" >/dev/null 2>&1 || true

RAW="${TMP}/vco.spice"
[ -f "${RAW}" ] || { echo "ERROR: xschem produced no netlist at ${RAW}" >&2; exit 1; }

GEN="${TMP}/vco.post"
{
  echo "* gf180-pll :: VCO netlist exported from design/vco.sch by design/netlist.sh"
  echo "* Do not edit by hand -- edit the schematics and re-run design/netlist.sh."
  # Uncomment the top-level subckt wrapper; drop the trailing .end (this file is
  # included by testbenches, it is not a deck on its own).
  sed -e 's/^\*\*\.subckt/.subckt/' -e 's/^\*\*\.ends/.ends/' -e '/^\.end$/d' "${RAW}"
} >"${GEN}"

if [ "${1:-}" = "--check" ]; then
  if diff -u "${OUT}" "${GEN}"; then
    echo "design/netlist.sh --check: netlist matches the schematics"
  else
    echo "ERROR: design/netlist/vco.spice is stale -- re-run design/netlist.sh" >&2
    exit 1
  fi
else
  mkdir -p "${HERE}/netlist"
  cp "${GEN}" "${OUT}"
  echo "wrote ${OUT}"
fi
