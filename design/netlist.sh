#!/usr/bin/env bash
# gf180-pll :: export an xschem schematic hierarchy to SPICE.
#
# One exporter serves every block captured in design/.  Each top has its own
# export CONVENTION, and the convention is a property of the block, not of the
# script -- so the top is selected explicitly rather than inferred:
#
#   ./design/netlist.sh [--top vco] [--check]
#       Regenerates the COMMITTED export design/netlist/vco.spice from
#       design/vco.sch.  `--check` regenerates into a temp dir and diffs
#       instead of writing, so a stale committed netlist fails loudly.
#       This is the default top, so bare `./design/netlist.sh` and
#       `./design/netlist.sh --check` keep the meaning design/README.md has
#       advertised since the VCO landed.
#
#   ./design/netlist.sh --top pfd_cp [outdir]
#       Exports the WHOLE pfd_cp hierarchy to <outdir>/dut.spice as an
#       includable fragment (default outdir: a temp dir, path echoed on
#       stdout).  This export is deliberately NOT committed -- each evidence
#       record freezes its own copy under
#       sim/<slug>/netlist-snapshots/<record-id>.spice (see sim/README.md).
#
# Why the two conventions differ, rather than one of them being wrong:
#   - The VCO is a single self-contained subcircuit whose export is small and
#     stable, so committing it makes the netlist reviewable in a diff and gives
#     `--check` something to check against.
#   - The PFD/CP is a nine-cell hierarchy re-exported per campaign; committing
#     it would add a second source of truth beside the per-record snapshot the
#     evidence actually cites.
# Both remain available; adding a third top means adding a case below, not
# forking this script.
#
# Why the pfd_cp export uses an export ROOT (`dut_export.sch`) rather than
# netlisting `pfd_cp.sch` directly: xschem emits real `.subckt` blocks for
# cells instantiated from a parent schematic, but only a commented `**.subckt`
# for the schematic it was asked to netlist.  `dut_export.sch` is a
# one-instance wrapper whose only job is to make pfd_cp a child, so pfd_cp
# itself comes out as a usable `.subckt`.  The VCO path takes the other route
# to the same place -- it netlists vco.sch directly and un-comments the wrapper
# -- because that keeps the committed file a line-for-line rendering of one
# schematic.
#
# Requires: xschem on PATH, and the gf180mcu PDK at $GF180_PDK_ROOT
# (default ~/.volare/gf180mcuD), the same variable sim/lib/simenv.sh uses.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat >&2 <<'EOF'
usage: netlist.sh [--top vco] [--check]
       netlist.sh --top pfd_cp [outdir]

  --top <vco|pfd_cp>  which schematic hierarchy to export (default: vco)
  --check             vco only: diff against the committed export, do not write
  outdir              pfd_cp only: where to write dut.spice (default: a temp dir)
EOF
}

TOP="vco"
CHECK=0
OUTDIR=""

while [ $# -gt 0 ]; do
  case "$1" in
    --top)     TOP="${2:-}"
               [ -n "${TOP}" ] || { echo "ERROR: --top needs a value" >&2; usage; exit 2; }
               shift 2 ;;
    --top=*)   TOP="${1#--top=}"; shift ;;
    --check)   CHECK=1; shift ;;
    -h|--help) usage; exit 0 ;;
    -*)        echo "ERROR: unknown option '$1'" >&2; usage; exit 2 ;;
    *)         [ -z "${OUTDIR}" ] || { echo "ERROR: more than one outdir given" >&2; usage; exit 2; }
               OUTDIR="$1"; shift ;;
  esac
done

command -v xschem >/dev/null 2>&1 || {
  echo "ERROR: xschem not found on PATH (brew install xschem)" >&2
  exit 1
}

# ------------------------------------------------------------ shared check --
# Guard against the silent failure mode described in design/xschemrc: if the
# devices/ library is not on XSCHEM_LIBRARY_PATH, xschem still "succeeds" but
# every net is auto-named and the connectivity is wrong.  Three cheap
# invariants catch it -- the expected subcircuits must exist, no `.subckt` port
# list may contain an auto-generated `netN` name, and no pin may be reported
# unconnected -- and they are applied to BOTH exports, so neither top can go
# out with silently-wrong connectivity.
check_export() {
  local netlist="$1"; shift
  local cell
  for cell in "$@"; do
    grep -qiE "^\.subckt +${cell}( |$)" "${netlist}" || {
      echo "ERROR: .subckt ${cell} missing from ${netlist}" >&2
      exit 1
    }
  done
  if grep -iE "^\.subckt " "${netlist}" | grep -qE '\bnet[0-9]+\b'; then
    echo "ERROR: auto-generated net names in a .subckt port list -- xschem could" >&2
    echo "       not resolve the label symbols (check XSCHEM_LIBRARY_PATH)." >&2
    exit 1
  fi
  if grep -q "IS MISSING" "${netlist}"; then
    echo "ERROR: unconnected pin(s) reported by xschem:" >&2
    grep "IS MISSING" "${netlist}" >&2
    exit 1
  fi
}

# ---------------------------------------------------------------- top: vco --
# Committed export.  xschem netlists a top-level schematic with its own
# .subckt/.ends lines commented out (`**.subckt vco ...`), because a top sheet
# is normally a testbench.  This block IS a subcircuit, so the two comment
# markers are uncommented here.  That is the whole post-processing step: no
# other line of the xschem output is altered, so the committed netlist stays a
# faithful export of design/vco.sch.
netlist_vco() {
  [ -z "${OUTDIR}" ] || {
    echo "ERROR: --top vco writes the committed export design/netlist/vco.spice;" >&2
    echo "       it takes no outdir.  Did you mean: --top pfd_cp ${OUTDIR}" >&2
    exit 2
  }

  local out="${HERE}/netlist/vco.spice"
  local top="${HERE}/vco.sch"
  local tmp raw gen
  tmp="$(mktemp -d)"
  # shellcheck disable=SC2064  # expand ${tmp} now, not when the trap fires
  trap "rm -rf '${tmp}'" EXIT

  # -n netlist, -s spice format, -q quit when done, -x no GUI.
  # xschem 3.4.7 exits 10 on a successful `-q` batch netlist, so the exit
  # status is deliberately ignored; the netlist file's existence is the
  # success check.
  xschem -n -s -q -x --rcfile "${HERE}/xschemrc" \
    --netlist_path "${tmp}" "${top}" >/dev/null 2>&1 || true

  raw="${tmp}/vco.spice"
  [ -f "${raw}" ] || { echo "ERROR: xschem produced no netlist at ${raw}" >&2; exit 1; }

  gen="${tmp}/vco.post"
  {
    echo "* gf180-pll :: VCO netlist exported from design/vco.sch by design/netlist.sh"
    echo "* Do not edit by hand -- edit the schematics and re-run design/netlist.sh."
    # Uncomment the top-level subckt wrapper; drop the trailing .end (this file
    # is included by testbenches, it is not a deck on its own).
    sed -e 's/^\*\*\.subckt/.subckt/' -e 's/^\*\*\.ends/.ends/' -e '/^\.end$/d' "${raw}"
  } >"${gen}"

  check_export "${gen}" vco vco_bias vco_stage

  if [ "${CHECK}" -eq 1 ]; then
    if diff -u "${out}" "${gen}"; then
      echo "design/netlist.sh --check: netlist matches the schematics"
    else
      echo "ERROR: design/netlist/vco.spice is stale -- re-run design/netlist.sh" >&2
      exit 1
    fi
  else
    mkdir -p "${HERE}/netlist"
    cp "${gen}" "${out}"
    echo "wrote ${out}"
  fi
}

# ------------------------------------------------------------- top: pfd_cp --
# Per-record export.  Writes <outdir>/dut.spice containing a `.subckt`
# definition for pfd_cp and every cell below it (pfd, cp, cp_leg_n, cp_leg_p,
# srlatch, edgedet, nand2_3v3, inv_3v3).  The stimulus decks under sim/
# `.include` that file and instantiate the block they are testing.
netlist_pfd_cp() {
  [ "${CHECK}" -eq 0 ] || {
    echo "ERROR: --check compares against a committed export; --top pfd_cp is" >&2
    echo "       exported per record into an outdir and is never committed" >&2
    echo "       (see sim/README.md)." >&2
    exit 2
  }

  local outdir="${OUTDIR:-$(mktemp -d)}"
  mkdir -p "${outdir}"

  # xschem exits 10 on a successful `--quit` after netlisting, not 0.
  local rc=0
  ( cd "${HERE}" && XSCHEM_NETLIST_DIR="${outdir}" \
      xschem --netlist --quit --no_x --rcfile "${HERE}/xschemrc" \
        "${HERE}/dut_export.sch" >"${outdir}/xschem.log" 2>&1 ) || rc=$?
  if [ "${rc}" -ne 0 ] && [ "${rc}" -ne 10 ]; then
    echo "ERROR: xschem netlist failed (exit ${rc}); see ${outdir}/xschem.log" >&2
    exit 1
  fi

  local raw="${outdir}/dut_export.spice"
  [ -f "${raw}" ] || { echo "ERROR: ${raw} not produced" >&2; exit 1; }

  # Make the export INCLUDABLE.  xschem's output is a standalone deck: it
  # carries the export root's own body as live top-level cards (only the
  # `.subckt` / `.ends` wrapper lines are commented out, not the instance
  # inside them) and it terminates with `.end`.  Included verbatim from a
  # stimulus deck, that would (a) instantiate a second, stray copy of the DUT
  # at top level and (b) end the deck at the `.end`, silently discarding
  # everything the including deck adds afterwards.  Strip both.
  local netlist="${outdir}/dut.spice"
  awk '
    /^\*\*\.subckt[ \t]+dut_export/ { skip = 1 }
    skip { if ($0 ~ /^\*\*\.ends/) skip = 0; next }
    /^[ \t]*\.end[ \t]*$/ { next }
    { print }
  ' "${raw}" >"${netlist}"

  check_export "${netlist}" pfd_cp pfd cp cp_leg_n cp_leg_p srlatch edgedet nand2_3v3 inv_3v3

  echo "${netlist}"
}

case "${TOP}" in
  vco)    netlist_vco ;;
  pfd_cp) netlist_pfd_cp ;;
  *)      echo "ERROR: unknown --top '${TOP}' (expected vco or pfd_cp)" >&2; usage; exit 2 ;;
esac
