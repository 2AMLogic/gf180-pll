#!/usr/bin/env bash
#
# Fails if this repository's two reader-facing status documents --
# README.md and docs/chipalooza/challenge-5-proposal.md -- disagree with
# what is actually committed under layout/evidence/ about PLL-block layout.
#
# Why this exists (issue #237). Both documents were written when `layout/`
# genuinely held nothing but the inverter proof-of-flow test cell, and both
# said so in as many words: "No PLL block has been drawn yet" (README.md)
# and "**No PLL-block layout exists.**" (the proposal, section 6). Four
# transistor-level sub-blocks then landed -- vco_block (#293), pfd_cp
# (#294), divider_chain (#295), lock_detector (#296) -- each with committed
# GDS and a DRC-clean evidence directory, and neither document moved. The
# stale sentences survived roughly five weeks and were quoted forward as
# fact by this repo's own issue tracker.
#
# This is the same drift sim/lib/check-readme-status.sh was written for
# (issue #117: a hand-written record count that silently under-reported the
# tree for months), in the other half of the repository. The fix is the
# same: derive the claim from the tree and make disagreement a build
# failure, rather than trusting prose to be re-read.
#
# The check is deliberately two-sided. It fails when a document *under*-
# states the tree (the drift that already happened) and when it *over*-
# states it -- e.g. once an assembled `pll_top` GDS lands, the "no
# assembled pll_top GDS" sentinel every document currently carries becomes
# false and must be removed, which is the next drift due.
#
# Usage: layout/lib/check-layout-status-claims.sh
# Exit codes: 0 all claims match the tree, 1 any mismatch.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EVIDENCE="${REPO_ROOT}/layout/evidence"

# The four PLL sub-blocks that together make up the block-level layout, and
# the block-level (not leaf-cell, not sub-block) artifact each one's own
# evidence directory publishes. Leaf-cell proof directories -- cp-leg-proof,
# divider-inv-proof, pfdcp-inv-proof and friends -- are deliberately NOT
# counted here: they prove a generator, not a drawn PLL block, and counting
# them is how "17 layouts!" becomes a claim nobody can check.
#
#   <block label>|<evidence dir>|<block GDS basename>|<LVS top cell>
BLOCKS=(
  "VCO|vco-layout|vco_block.gds|vco_block"
  "PFD + charge pump|pfd-cp-layout|pfd_cp.gds|pfd_cp"
  "divider chain|divider-chain-layout|divider_chain.gds|divider_chain"
  "lock detector|lock-detector-layout|lock_detector.gds|lock_detector"
)

# Documents whose prose is checked, relative to the repo root.
DOCS=(
  "README.md"
  "docs/chipalooza/challenge-5-proposal.md"
)

status=0

fail() {
  echo "FAIL: $*" >&2
  status=1
}

# --- Derive the real state from the committed evidence tree ----------------

drawn=0
lvs_matched=0
summary=()

for entry in "${BLOCKS[@]}"; do
  IFS='|' read -r label dir gds top <<<"${entry}"

  has_gds=no
  has_drc=no
  has_lvs=no

  [ -f "${EVIDENCE}/${dir}/${gds}" ] && has_gds=yes

  # A DRC-clean claim needs the recorded deck output, not just a directory.
  if compgen -G "${EVIDENCE}/${dir}/drc-clean/*.log" >/dev/null 2>&1; then
    has_drc=yes
  fi

  # An LVS claim needs the PDK deck's own verdict line in the recorded log.
  # "Congratulations! Netlists match." is run_lvs.py's match verdict; its
  # absence is how pfd_cp and lock_detector correctly read as unmatched
  # today, both of which say so explicitly in their own PROOF.md.
  if compgen -G "${EVIDENCE}/${dir}/lvs-clean/*.log" >/dev/null 2>&1 &&
    grep -qF "Netlists match." "${EVIDENCE}/${dir}"/lvs-clean/*.log 2>/dev/null; then
    has_lvs=yes
  fi

  if [ "${has_gds}" = yes ] && [ "${has_drc}" = yes ]; then
    drawn=$((drawn + 1))
  fi
  [ "${has_lvs}" = yes ] && lvs_matched=$((lvs_matched + 1))

  summary+=("$(printf '  %-20s gds=%-3s drc-clean=%-3s lvs-matched=%-3s (%s)' \
    "${label}" "${has_gds}" "${has_drc}" "${has_lvs}" "${top}")")
done

# Is there an assembled top level? Nothing in the tree publishes one today;
# when one lands it will be a committed GDS under an evidence directory,
# same as every block above.
top_assembled=no
if compgen -G "${EVIDENCE}/*/pll_top.gds" >/dev/null 2>&1; then
  top_assembled=yes
fi

echo "layout/evidence/ says:"
printf '%s\n' "${summary[@]}"
echo "  assembled pll_top GDS: ${top_assembled}"
echo

# --- Check each document's prose against it -------------------------------

# Sentinel phrases. Each is a literal substring the document must contain
# (or, for the forbidden list, must not) after whitespace collapsing, so
# prose may wrap freely.
drawn_claim="${drawn} of the 4 PLL sub-blocks"
lvs_claim="${lvs_matched} of the 4 are LVS-matched"
no_top_claim="no assembled \`pll_top\` GDS"

# Claims that were true before any block was drawn and are false after.
# Checked only while the tree actually has drawn blocks, so this script
# stays correct if the evidence tree is ever emptied.
#
# These are matched as literal substrings of the whitespace-collapsed
# document, so a document may not quote one of them even to describe it as
# historical -- paraphrase instead. That is deliberate: a matcher that tried
# to tell "asserting this" from "quoting this" would be guessing.
FORBIDDEN_ONCE_DRAWN=(
  "No PLL block has been drawn yet"
  "No PLL-block layout exists"
  "PLL-block GDS/reports not yet drawn"
)

for doc in "${DOCS[@]}"; do
  path="${REPO_ROOT}/${doc}"
  if [ ! -f "${path}" ]; then
    fail "${doc} does not exist"
    continue
  fi

  flat="$(tr '\n' ' ' <"${path}" | tr -s ' ')"

  if ! printf '%s' "${flat}" | grep -qF "${drawn_claim}"; then
    fail "${doc} does not state \"${drawn_claim}\" -- ${drawn} of the 4 sub-blocks have a committed GDS plus a DRC-clean log under layout/evidence/"
  fi

  if ! printf '%s' "${flat}" | grep -qF "${lvs_claim}"; then
    fail "${doc} does not state \"${lvs_claim}\" -- ${lvs_matched} of the 4 sub-blocks have an LVS log recording \"Netlists match.\""
  fi

  if [ "${top_assembled}" = no ]; then
    if ! printf '%s' "${flat}" | grep -qF "${no_top_claim}"; then
      fail "${doc} does not state \"${no_top_claim}\" -- no assembled top-level GDS is committed, and a reader must not have to infer that"
    fi
  else
    if printf '%s' "${flat}" | grep -qF "${no_top_claim}"; then
      fail "${doc} still says \"${no_top_claim}\", but an assembled pll_top GDS is now committed under layout/evidence/"
    fi
  fi

  if [ "${drawn}" -gt 0 ]; then
    for phrase in "${FORBIDDEN_ONCE_DRAWN[@]}"; do
      if printf '%s' "${flat}" | grep -qF "${phrase}"; then
        fail "${doc} still says \"${phrase}\", but ${drawn} PLL sub-block layout(s) are committed under layout/evidence/"
      fi
    done
  fi
done

if [ "${status}" -eq 0 ]; then
  echo "OK: README.md and docs/chipalooza/challenge-5-proposal.md match layout/evidence/" \
    "(${drawn}/4 drawn + DRC-clean, ${lvs_matched}/4 LVS-matched, assembled pll_top: ${top_assembled})"
fi

exit "${status}"
