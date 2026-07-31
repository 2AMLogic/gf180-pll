#!/usr/bin/env bash
# gf180-pll :: export the xschem schematic hierarchies under design/ to SPICE.
#
#   ./design/netlist.sh                    # regenerate design/netlist/*.spice
#   ./design/netlist.sh --check            # regenerate into a temp dir and diff
#   ./design/netlist.sh --top <block>      # regenerate one committed block
#   ./design/netlist.sh --top pfd_cp [dir] # per-record export (NOT committed)
#   ./design/netlist.sh --check-paths      # assert the symbol search path
#
# One exporter serves every block captured in design/.  There are two export
# CONVENTIONS, and the convention is a property of the block, not of the
# script:
#
#   COMMITTED (BLOCKS below: vco, div23_cell, divider_chain, lock_detector,
#   dff_tg_3v3) -- each top is netlisted with its full hierarchy into one
#   self-contained file under design/netlist/, which is committed.  `--check`
#   regenerates into a temp dir and diffs instead of writing, so a stale
#   committed netlist fails loudly.  These exports are small and stable, so
#   committing them makes the netlist reviewable in a diff and gives `--check`
#   something to check against.
#
#   PER-RECORD (pfd_cp) -- the whole hierarchy is exported to <outdir>/dut.spice
#   as an includable fragment and is deliberately NOT committed: each evidence
#   record freezes its own copy under
#   sim/<slug>/netlist-snapshots/<record-id>.spice (see sim/README.md).  The
#   PFD/CP is a nine-cell hierarchy re-exported per campaign; committing it
#   would add a second source of truth beside the per-record snapshot the
#   evidence actually cites.
#
# Both remain available; adding a block means adding it to BLOCKS (or adding a
# case below), not forking this script.
#
# Never `.include` two exports in the same deck: each carries its own copy of
# the shared leaf cells (inv_3v3, nand2_3v3, vco_stage, ...), so including two
# would redefine them.  That hazard is also why leaf cells are NAMESPACED BY
# OWNING BLOCK -- see design/README.md "Leaf-cell ownership and naming" (the
# convention, from #30) and DR-004 (which cells are shared, and which the
# PFD/CP block owns).  The PFD/CP block owns `pfdcp_inv_3v3` /
# `pfdcp_nand2_3v3`, deliberately different cells from the shared library's
# `inv_3v3` / `nand2_3v3`.
#
# Every run -- `--check` and plain write mode alike -- performs a cross-block
# leaf-cell collision check (see check_leaf_cell_collisions below): every
# export is self-contained and inlines its own copy of every leaf cell it
# uses, captured whenever that top was last regenerated.  Two tops can
# therefore carry genuinely different bodies under the same `.subckt <name>`
# even though design/ only ever holds one `<name>.sch` at a time on disk --
# exactly the add/add-collision hazard this repo has hit twice.  The check
# hashes every `.subckt ... .ends` block across all exports and fails loudly
# if the same cell name hashes differently anywhere: `--check` exits non-zero
# without writing (it never writes), and plain write mode refuses to write or
# copy the colliding exports into design/netlist/ either -- see DR-004 item
# 4(b).
#
# **[#26 delta]** the check spans the per-record `pfd_cp` top as well as the
# committed ones.  The collision that motivated it was between `pfd_cp` and the
# committed divider/lock-detector tops, and `pfd_cp` has no committed export for
# the staleness diff to catch -- restricting the check to BLOCKS would have
# missed the one case it exists for.
#
# Why the pfd_cp export uses an export ROOT (`dut_export.sch`) rather than
# netlisting `pfd_cp.sch` directly: xschem emits real `.subckt` blocks for
# cells instantiated from a parent schematic, but only a commented `**.subckt`
# for the schematic it was asked to netlist.  `dut_export.sch` is a
# one-instance wrapper whose only job is to make pfd_cp a child, so pfd_cp
# itself comes out as a usable `.subckt`.  The committed tops take the other
# route to the same place -- each is netlisted directly and the wrapper
# un-commented -- because that keeps a committed file a line-for-line rendering
# of one schematic.
#
# Requires: xschem on PATH, and the gf180mcu PDK at $GF180_PDK_ROOT
# (default ~/.volare/gf180mcuD), the same variable sim/lib/simenv.sh uses.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Committed tops a testbench instantiates: the ring VCO (#8) and the feedback
# divider / lock detector (#11).
BLOCKS=(vco div23_cell divider_chain lock_detector dff_tg_3v3)

# Expected `.subckt` set per top -- the connectivity guard below fails the run
# if any of these is missing from the corresponding export.
expected_subckts() {
  case "$1" in
    vco)            echo "vco vco_bias vco_stage" ;;
    div23_cell)     echo "div23_cell nand3_3v3 nand2_3v3 inv_3v3 dff_tg_3v3 inv2x_3v3 tgate_3v3" ;;
    divider_chain)  echo "divider_chain div23_cell nor2_3v3 inv_3v3 nand2_3v3 nand3_3v3 inv2x_3v3 dff_tg_3v3 tgate_3v3" ;;
    lock_detector)  echo "lock_detector xor2_3v3 delaywin_3v3 nand2_3v3 inv_3v3 schmitt_3v3" ;;
    dff_tg_3v3)     echo "dff_tg_3v3 inv_3v3 tgate_3v3" ;;
    pfd_cp)         echo "pfd_cp pfd cp cp_leg_n cp_leg_p srlatch edgedet pfdcp_nand2_3v3 pfdcp_inv_3v3" ;;
    *)              echo "" ;;
  esac
}

usage() {
  cat >&2 <<'EOF'
usage: netlist.sh [--top <block>] [--check]
       netlist.sh --top pfd_cp [outdir]
       netlist.sh --check-paths

  (no args)           regenerate every committed export under design/netlist/
  --top <block>       restrict to one top.  Committed tops: vco, div23_cell,
                      divider_chain, lock_detector, dff_tg_3v3.
                      The per-record top is pfd_cp.
  --check             committed tops only: diff against the committed export,
                      do not write
  --check-paths       assert the xschem symbol search path resolves bare and
                      qualified symbol names without shadowing
  outdir              pfd_cp only: where to write dut.spice (default: a temp dir)
EOF
}

TOP=""
CHECK=0
CHECK_PATHS=0
OUTDIR=""

while [ $# -gt 0 ]; do
  case "$1" in
    --top)         TOP="${2:-}"
                   [ -n "${TOP}" ] || { echo "ERROR: --top needs a value" >&2; usage; exit 2; }
                   shift 2 ;;
    --top=*)       TOP="${1#--top=}"; shift ;;
    --check)       CHECK=1; shift ;;
    --check-paths) CHECK_PATHS=1; shift ;;
    -h|--help)     usage; exit 0 ;;
    -*)            echo "ERROR: unknown option '$1'" >&2; usage; exit 2 ;;
    *)             [ -z "${OUTDIR}" ] || { echo "ERROR: more than one outdir given" >&2; usage; exit 2; }
                   OUTDIR="$1"; shift ;;
  esac
done

command -v xschem >/dev/null 2>&1 || {
  echo "ERROR: xschem not found on PATH (brew install xschem)" >&2
  exit 1
}

XSCHEM_VERSION="$(xschem --no_x -q --version 2>/dev/null | head -1 || echo 3.4.7)"

# ------------------------------------------------------------- path assert --
# design/xschemrc puts BOTH the leaf symbol directories (so `pfet_03v3.sym`
# resolves) and their PARENTS (so `symbols/pfet_03v3.sym` resolves) on
# XSCHEM_LIBRARY_PATH, because the blocks in design/ were captured with
# different reference styles.  That union is only safe as long as the parent
# directories hold no `.sym` of their own -- otherwise a parent could shadow
# the leaf, and a bare reference would silently bind to a different symbol.
# The argument is easy to state and easy to invalidate when the PDK or the
# xschem install moves, so it is asserted here rather than left in a comment.
check_paths() {
  local pdk="${GF180_PDK_ROOT:-${HOME}/.volare/gf180mcuD}"
  local sharedir=""
  local xbin
  xbin="$(command -v xschem)"
  for cand in \
      "$(dirname "${xbin}")/../share/xschem" \
      "/opt/homebrew/share/xschem" \
      "/usr/local/share/xschem" \
      "/usr/share/xschem"; do
    if [ -d "${cand}/xschem_library" ]; then sharedir="${cand}"; break; fi
  done
  [ -n "${sharedir}" ] || {
    echo "ERROR: could not locate XSCHEM_SHAREDIR (no xschem_library found)" >&2
    return 1
  }

  local rc=0 parent stray
  for parent in "${sharedir}/xschem_library" "${pdk}/libs.tech/xschem"; do
    if [ ! -d "${parent}" ]; then
      echo "WARN: symbol-path parent ${parent} does not exist -- skipped" >&2
      continue
    fi
    stray="$(find "${parent}" -maxdepth 1 -name '*.sym' 2>/dev/null | head -5)"
    if [ -n "${stray}" ]; then
      echo "ERROR: ${parent} now holds .sym file(s) of its own:" >&2
      echo "${stray}" >&2
      echo "       Those can shadow a bare symbol reference that is supposed to" >&2
      echo "       resolve in the leaf directory below it.  See design/xschemrc." >&2
      rc=1
    else
      echo "ok: no .sym directly under ${parent}"
    fi
  done
  return "${rc}"
}

if [ "${CHECK_PATHS}" -eq 1 ]; then
  { [ -z "${TOP}" ] && [ -z "${OUTDIR}" ] && [ "${CHECK}" -eq 0 ]; } || {
    echo "ERROR: --check-paths takes no other arguments" >&2; usage; exit 2; }
  check_paths
  echo "design/netlist.sh --check-paths: symbol search path is unshadowed"
  exit 0
fi

# ------------------------------------------------------------ shared check --
# Guard against the silent failure mode described in design/xschemrc: if the
# devices/ library is not on XSCHEM_LIBRARY_PATH, xschem still "succeeds" but
# every net is auto-named and the connectivity is wrong.  Three cheap
# invariants catch it -- the expected subcircuits must exist, no `.subckt` port
# list may contain an auto-generated `netN` name, and no pin may be reported
# unconnected -- and they are applied to EVERY export, so no top can go out
# with silently-wrong connectivity.
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

# ------------------------------------------------------------- path stamps --
# xschem stamps the absolute path of every .sch/.sym it expands into a comment
# (`** sch_path: /abs/checkout/design/foo.sch`).  That path is whichever
# checkout the file was generated in, so a byte-exact comparison -- or a
# byte-exact snapshot hash -- is otherwise machine-specific (#28).  Those
# comment lines, and only those, are rewritten to repo-relative form; every
# other byte, including everything ngspice reads, is untouched.  Applied at
# WRITE time by both export conventions (export_block and netlist_pfd_cp), and
# again on both sides of the `--check` diff -- the second pass is a no-op on
# output this script wrote, and is kept as defense in depth against a committed
# file minted before write-time normalization existed.
#
# Writes to a file rather than a pipeline so that a sed failure aborts the run
# (`set -e`) instead of silently producing two empty streams that compare equal.
normalize() {
  sed -E 's#^(\*\* (sch|sym)_path: ).*/design/#\1design/#' "$1" >"$2"
}

# Two-line banner prepended to each committed export.  `vco.spice` and the
# divider / lock-detector exports were minted by two different generations of
# this script and carry different wording; both are reproduced verbatim on
# purpose.  The `sim/` evidence records pin the SHA-256 of the netlist each
# campaign actually simulated, and the committed exports still hash equal to
# those snapshots -- rewording a comment line would break that chain for no
# benefit.
banner() {
  case "$1" in
    vco)
      printf '%s\n' \
        "* gf180-pll :: VCO netlist exported from design/vco.sch by design/netlist.sh" \
        "* Do not edit by hand -- edit the schematics and re-run design/netlist.sh."
      ;;
    *)
      printf '%s\n' \
        "* gf180-pll :: $1 -- generated by design/netlist.sh from $1.sch" \
        "* xschem ${XSCHEM_VERSION}; do not edit by hand."
      ;;
  esac
}

# -------------------------------------------------------- committed export --
# PATH-INDEPENDENT BYTES (#28): the committed exports below are `normalize`d at
# WRITE time, exactly like the per-record pfd_cp export -- both conventions now
# produce identical bytes from any checkout path.  This closes the gap an
# earlier revision of this script left open, where only the `--check`
# comparison was normalized while the committed bytes still embedded the
# absolute path of the checkout that generated them.
#
# Normalizing at write time changed the committed bytes (comment lines only --
# no device card, port list or `.subckt`/`.ends` block moved), which
# invalidates the netlist-snapshot SHA-256 that the sim/vco-tuning-range,
# sim/divider-ratio and sim/lock-detector records cite.  sim/README.md's
# append-only rule therefore requires those campaigns to be re-run and
# re-minted under new record IDs; that re-run is tracked separately in #32 and
# #28 stays open until it lands.  The existing records are NOT edited.
export_block() {
  local blk="$1" outdir="$2" work="$3"

  # -n netlist, -s spice format, -q quit when done, --no_x no GUI, -o out dir.
  # xschem 3.4.7 can exit non-zero on a successful `-q` batch netlist, so the
  # exit status is deliberately ignored; the netlist file's existence is the
  # success check.
  (cd "${HERE}" && xschem --no_x -n -s -q \
      --rcfile "${HERE}/xschemrc" -o "${work}" "${HERE}/${blk}.sch" >/dev/null 2>&1) || true

  [ -f "${work}/${blk}.spice" ] || {
    echo "ERROR: xschem produced no netlist for ${blk} at ${work}/${blk}.spice" >&2
    exit 1
  }

  {
    banner "${blk}"
    # Promote the top cell's commented `**.subckt` header to a real one and
    # drop the trailing `.end`, so the file is `.include`-able by a testbench.
    sed -e 's/^\*\*\.subckt/.subckt/' \
        -e 's/^\*\*\.ends/.ends/' \
        -e '/^\.end$/d' \
        "${work}/${blk}.spice"
  } >"${work}/${blk}.raw.spice"

  # Reuse normalize() (see above) at write time, not just at --check compare
  # time, so the committed bytes never embed the exporting checkout's absolute
  # path in the first place -- a re-export from any checkout now produces an
  # identical file.  normalize() is idempotent on already-relative input (its
  # pattern only matches a path segment preceding "/design/", which a relative
  # "design/..." path lacks), so --check's own normalize() over this
  # already-relative output is a harmless no-op.
  normalize "${work}/${blk}.raw.spice" "${outdir}/${blk}.spice"

  # shellcheck disable=SC2046  # word splitting of the cell list is intended
  check_export "${outdir}/${blk}.spice" $(expected_subckts "${blk}")
}

# ------------------------------------------------------------- top: pfd_cp --
# Per-record export.  Writes <outdir>/dut.spice containing a `.subckt`
# definition for pfd_cp and every cell below it (pfd, cp, cp_leg_n, cp_leg_p,
# srlatch, edgedet, pfdcp_nand2_3v3, pfdcp_inv_3v3).  The stimulus decks under sim/
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
  ' "${raw}" >"${outdir}/dut.raw"

  # Path-independent bytes (#28): the snapshot SHA-256 an evidence record cites
  # must be reproducible on any machine, not only in the checkout that minted
  # it.  Same write-time `normalize` the committed tops get in export_block --
  # both export conventions are path-independent at write time.
  normalize "${outdir}/dut.raw" "${netlist}"
  rm -f "${outdir}/dut.raw"

  if grep -qE '^\*\* (sch|sym)_path: /' "${netlist}"; then
    echo "ERROR: ${netlist} still embeds absolute sch_path/sym_path comments" >&2
    exit 1
  fi

  # shellcheck disable=SC2046  # word splitting of the cell list is intended
  check_export "${netlist}" $(expected_subckts pfd_cp)

  echo "${netlist}"
}

# ------------------------------------------------- leaf-cell collision check --
# The mechanical half of the "Leaf-cell ownership and naming" convention in
# design/README.md (#30/#31), extended to cover the per-record `pfd_cp` top.
#
# Every export is self-contained: it inlines its own copy of every leaf cell it
# uses.  Two tops can therefore carry genuinely different bodies under the same
# `.subckt <name>` even though design/ only ever holds one `<name>.sch` at a
# time -- which is precisely how #26 and #27 each shipped a different
# `inv_3v3`.  Byte-identical content under one name across several tops is
# expected (the shared library) and is NOT a failure; only real divergence is.
sha256_of_stdin() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum | awk '{print $1}'
  else
    shasum -a 256 | awk '{print $1}'
  fi
}

# Extracts every `.subckt <name> ... .ends` block from an export and records a
# content hash for each, so the same leaf-cell name can be compared across every
# top that defines it.  `celldir` gets one file per cell name, appended with one
# `<top>\t<hash>` line per top that defines that cell -- if a cell's hash set
# ever holds more than one distinct value, two tops disagree about what that
# cell is.
record_subckt_hashes() {
  local blk="$1" file="$2" celldir="$3" name hash
  while IFS= read -r name; do
    [ -n "${name}" ] || continue
    hash="$(awk -v n="${name}" '
              $0 ~ "^\\.subckt " n "( |$)" { capturing=1 }
              capturing { print }
              /^\.ends/ && capturing { exit }
            ' "${file}" | sha256_of_stdin)"
    printf '%s\t%s\n' "${blk}" "${hash}" >>"${celldir}/${name}"
  done < <(grep '^\.subckt ' "${file}" | awk '{print $2}')
}

# Fails loudly if any leaf-cell name resolves to genuinely different content
# across the exports it appears in.  Takes `<top>=<export-path>` pairs so the
# uncommitted pfd_cp export can take part alongside the committed ones.
check_leaf_cell_collisions() {
  local celldir cellfile cellname nuniq rc=0 pair blk file
  celldir="$(mktemp -d)"

  for pair in "$@"; do
    blk="${pair%%=*}"
    file="${pair#*=}"
    [ -f "${file}" ] || continue
    record_subckt_hashes "${blk}" "${file}" "${celldir}"
  done

  for cellfile in "${celldir}"/*; do
    [ -e "${cellfile}" ] || continue
    cellname="$(basename "${cellfile}")"
    nuniq="$(awk -F'\t' '{print $2}' "${cellfile}" | sort -u | wc -l | tr -d ' ')"
    if [ "${nuniq}" -gt 1 ]; then
      echo "ERROR: leaf-cell '${cellname}' diverges across tops (add/add collision):" >&2
      awk -F'\t' '{print "  " $1 " -> " $2}' "${cellfile}" | sort -u >&2
      echo "       A leaf cell is owned by one block and named for it --" >&2
      echo "       see design/README.md \"Leaf-cell ownership and naming\" and DR-004." >&2
      rc=1
    fi
  done

  rm -rf "${celldir}"
  return "${rc}"
}
# ------------------------------------------------------------------ driver --
if [ "${TOP}" = "pfd_cp" ]; then
  netlist_pfd_cp
  exit 0
fi

[ -z "${OUTDIR}" ] || {
  echo "ERROR: the committed tops write design/netlist/<block>.spice; they take" >&2
  echo "       no outdir.  Did you mean: --top pfd_cp ${OUTDIR}" >&2
  exit 2
}

SELECTED=("${BLOCKS[@]}")
if [ -n "${TOP}" ]; then
  found=0
  for blk in "${BLOCKS[@]}"; do
    [ "${blk}" = "${TOP}" ] && found=1
  done
  [ "${found}" -eq 1 ] || {
    echo "ERROR: unknown --top '${TOP}' (expected one of: ${BLOCKS[*]} pfd_cp)" >&2
    usage; exit 2
  }
  SELECTED=("${TOP}")
fi

WORK="$(mktemp -d)"
GENDIR="$(mktemp -d)"
trap 'rm -rf "${WORK}" "${GENDIR}"' EXIT

for blk in "${SELECTED[@]}"; do
  [ -f "${HERE}/${blk}.sch" ] || {
    echo "ERROR: no schematic at design/${blk}.sch" >&2
    exit 1
  }
  export_block "${blk}" "${GENDIR}" "${WORK}"
done

# Inputs to the cross-top collision check, as `<top>=<path>` pairs.
#
# The COMMITTED exports are compared, not the freshly regenerated ones.  That
# is deliberate and is the only version of this check that can ever fire: each
# committed export is frozen at whatever the schematics said when that top was
# last regenerated, so two of them can disagree.  A set of exports all
# regenerated in the same run cannot disagree in a flat namespace -- one
# `<name>.sch` on disk yields one body -- so comparing regenerated files would
# be a check that always passes.
COLLISION_INPUTS=()
for blk in "${BLOCKS[@]}"; do
  COLLISION_INPUTS+=("${blk}=${HERE}/netlist/${blk}.spice")
done

# **[#26 delta]** the per-record pfd_cp top takes part too, from its FRESH
# export -- it has no committed file to read.  This is the half that catches
# the #26/#27 case: pfd_cp is regenerated from today's schematics while the
# committed tops carry frozen copies, so a PFD/CP hierarchy that reaches into a
# shared-list cell it has re-sized shows up here as a divergence.  Without it,
# pfd_cp is the one top a collision passes through silently, because it has no
# committed export for the staleness diff to catch either.  A
# `--top <one-block>` run has nothing useful to compare, so it is skipped.
if [ "${#SELECTED[@]}" -eq "${#BLOCKS[@]}" ]; then
  (
    cd "${HERE}" && XSCHEM_NETLIST_DIR="${WORK}" \
      xschem --netlist --quit --no_x --rcfile "${HERE}/xschemrc" \
        "${HERE}/dut_export.sch" >"${WORK}/xschem-pfd_cp.log" 2>&1
  ) || true
  [ -f "${WORK}/dut_export.spice" ] || {
    echo "ERROR: the pfd_cp export needed for the leaf-cell collision check was" >&2
    echo "       not produced; see ${WORK}/xschem-pfd_cp.log" >&2
    exit 1
  }
  COLLISION_INPUTS+=("pfd_cp=${WORK}/dut_export.spice")
fi

collisions_rc=0
check_leaf_cell_collisions "${COLLISION_INPUTS[@]}" || collisions_rc=1

if [ "${CHECK}" -eq 1 ]; then
  rc="${collisions_rc}"
  for blk in "${SELECTED[@]}"; do
    committed="${HERE}/netlist/${blk}.spice"
    if [ ! -f "${committed}" ]; then
      echo "STALE: design/netlist/${blk}.spice is missing -- run design/netlist.sh" >&2
      rc=1
      continue
    fi
    normalize "${committed}" "${WORK}/${blk}.committed.norm"
    normalize "${GENDIR}/${blk}.spice" "${WORK}/${blk}.regen.norm"
    if ! diff -u --label "design/netlist/${blk}.spice (committed)" \
                 --label "design/${blk}.sch (regenerated)" \
                 "${WORK}/${blk}.committed.norm" "${WORK}/${blk}.regen.norm"; then
      echo "STALE: design/netlist/${blk}.spice differs from ${blk}.sch" >&2
      rc=1
    fi
  done

  if [ "${rc}" -eq 0 ]; then
    echo "design/netlist.sh --check: all ${#SELECTED[@]} netlists match the schematics, no leaf-cell collisions"
  else
    echo "ERROR: design/netlist.sh --check failed -- see STALE / leaf-cell collision errors above" >&2
  fi
  exit "${rc}"
fi

# Write mode honors the same collisions_rc --check already exits on (DR-004
# item 4(b)): a detected leaf-cell collision is refused, not merely reported,
# so a plain `design/netlist.sh` run cannot silently commit a colliding set
# any more than `--check` can silently pass one. Nothing under
# design/netlist/ is touched when this fires.
if [ "${collisions_rc}" -ne 0 ]; then
  echo "ERROR: leaf-cell collision detected (see above) -- refusing to write" >&2
  echo "       design/netlist/*.spice.  Fix the colliding cell and re-run." >&2
  exit 1
fi

mkdir -p "${HERE}/netlist"
for blk in "${SELECTED[@]}"; do
  cp "${GENDIR}/${blk}.spice" "${HERE}/netlist/${blk}.spice"
  echo "netlisted ${blk} -> design/netlist/${blk}.spice"
done
