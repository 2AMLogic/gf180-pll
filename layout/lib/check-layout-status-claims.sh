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
# The first version of this script graded prose against a hand-written list
# of three forbidden sentences -- the exact three that had gone stale. That
# list cannot catch a *sibling* sentence, and it did not catch one in the
# very commit that introduced it: the same change that rewrote the
# proposal's section 6 left section 3 asserting "**No layout exists for
# this block** -- `layout/` currently contains only the DRC/LVS flow's
# proof-of-flow test cell", the identical claim in different words, and
# this check reported OK on that tree.
#
# So the list is no longer the mechanism; it is kept only for its precise
# error messages. The mechanism is the SCOPE RULE below: any sentence that
# asserts layout does *not* exist must say at what scope it does not exist
# (top level / assembled / post-layout / extracted), and an unscoped
# absence claim fails as soon as the tree holds a drawn block. A writer who
# invents new wording for "nothing is drawn" trips it; a writer who states
# the true, top-level-scoped absence does not. That is a property of the
# claim, not of a remembered sentence.
#
# A second, narrower guard covers the same drift class for `spec/pll.md`'s
# ratification state, which went stale in the same document for the same
# reason (section 5.0 was corrected to "ratified, with amendments"; section
# 1 kept saying the spec was "pending engineering ratification").
#
# A third guard, the FOOTPRINT RULE, covers the numbers rather than the
# prose. Existence was graded; size was not, and it drifted next. The
# proposal's section 6 table carried `vco_block` at 183.18 x 170.28 um
# (0.0312 mm2) -- the figure #324's fold produced, superseded when the
# high-Rs resistor re-shaped the block -- and `pfd_cp` at 347.41 x 73.23 um
# (0.0254 mm2), which is the `footprint` tuple (a union of recorded
# sub-block extents) rather than the drawn-shape bounding box the column
# header claims. Section 5 of the same document carried the correct,
# committed-GDS figures for both, so the proposal told an outside reader two
# different sizes for the same block. Four area-reduction levers landed in
# one week (#469/#470/#473/#477) and each one updated section 5 while
# leaving section 6's table behind, so this is drift with a demonstrated
# recurrence rate, not a one-off typo.
#
# The rule: every "W x H um" footprint stated in either document is
# attributed to the nearest block named before it, and must equal that
# block's row in layout/evidence/area-audit/area-audit.md -- the audit
# `python3 layout/run_pv.py area` regenerates from the committed GDS. Where
# a mm2 figure sits directly against such a tuple, it must equal the audit's
# bbox too. Two-sided, like everything else here: the proposal must also
# state a current footprint for every block the audit records, so a stale
# number cannot be "fixed" by deleting the column.
#
# A fourth guard, the COUNT RULE, covers a drift the drawn_claim/lvs_claim
# substring checks below cannot see: they only require the *correct* "N of
# the 4 ..." sentence to appear somewhere in the document, so a *second*,
# contradicting count elsewhere passes silently. That is exactly what
# happened: the same commit (#445) that correctly wrote "4 of the 4 are
# LVS-matched" in the proposal's maturity note and section 6 left section 3
# still saying "2 of the 4 are LVS-matched" a few paragraphs later, true
# only before #452/#466 landed the last two LVS matches. The count rule
# grades every occurrence of the claim, not just its presence once: any "N
# of the 4 [PLL] sub-blocks" or "N of the 4 [are] LVS-matched" phrase whose
# N disagrees with the tree fails, wherever in the document it sits.
#
# A fifth guard, added 2026-09-25, extends the footprint rule's reach rather
# than adding a new one. spec/pll.md's own "## Area" section states the same
# four "W x H um" block footprints README.md and the proposal do (it is the
# ratified spec's own accounting of what the 0.30 mm2 budget row now measures)
# and nothing graded it: this script's DOCS list has never included
# spec/pll.md, because the rest of the script's rules (the scope rule, the
# count rule, the two forbidden-phrase lists) do not fit a normative spec the
# way they fit a status narrative written for an outside reader. That left the
# one claim class already proven to drift on a recurring, roughly weekly
# cadence (four area-reduction levers in the single week noted above)
# ungraded in the one place it is also load-bearing: DR-016/DR-017's area
# budget is amended against these very numbers. Grading is scoped to the
# section's own text, not the whole file -- spec/pll.md also states unrelated
# device dimensions in the same "W x H um" shape (the loop filter's C2 plate,
# `31.4 x 31.4 um`, in the Loop bandwidth section), which have no row in
# area-audit.md and are not block footprints; a whole-document scan would
# misreport them as an unattributable claim. Requires a current footprint for
# all four blocks, like the proposal -- spec/pll.md's Area table already
# states all four.
#
# A sixth guard, the ERC RULE, added 2026-09-26 (issue #565), is the first one
# here that grades an *evidence artifact* against the tree rather than prose
# against the tree -- and it exists because the artifact it grades had already
# gone stale in three different ways at once while nothing noticed.
# `layout/evidence/vco-layout/erc-report.json` was the only `klt erc` supply
# report in the repository; its `file` field named a `/tmp/i433w/` scratch path
# no reader could open, its `provenance.klt_version` was `0.5.0` while CI had
# pinned 0.6.0 for weeks, and its spec's reason for declaring no `ties[]` cited
# an upstream bug that had been fixed five days earlier. Every one of those is a
# claim about a committed file that a committed file could have been checked
# against. Now each is:
#
#   * every block with committed LVS-clean evidence must also carry an
#     `erc-supply-spec.json`, an `erc-report.json` and a `PROOF-erc.md` --
#     coverage is derived from the tree, so "N of the 4 blocks ERC-checked" is a
#     fact this script prints rather than a sentence someone re-derives by hand;
#   * the report's `provenance.input.content_hash` must equal the committed
#     GDS's own sha256, and `provenance.spec.content_hash` the committed spec's
#     -- so a regenerated block with a stale ERC report beside it fails the
#     build instead of silently describing a layout that no longer exists;
#   * the report's `provenance.klt_version` must match the klt version
#     `.github/workflows/ci.yml` pins, read from that file rather than restated
#     here;
#   * a spec's top-level keys must come from `klt erc`'s own documented schema
#     (plus a `_description`). This is the structural half of the stale-rationale
#     fix: the `_ties_omitted` free-text key that carried the fixed-bug citation
#     is not merely removed, it is now unrepresentable. A deliberate zero-`ties[]`
#     declaration must use the first-class `ties_disclosure` field, whose
#     machine-readable `kind` a grader can actually act on;
#   * and every `PROOF-erc.md` must state its own report's antenna coverage
#     (`checked: 0, skipped: N`, reason `missing_antenna_pdk`) with N matching
#     the report, because the antenna half of `klt erc` has never run in this
#     repository and "`klt erc` was run" must never be read as broader than it is.
#
# Usage: layout/lib/check-layout-status-claims.sh
# Exit codes: 0 all claims match the tree, 1 any mismatch.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EVIDENCE="${REPO_ROOT}/layout/evidence"

# The machine-generated block-geometry audit the footprint rule grades
# against. Regenerated by `python3 layout/run_pv.py area` from the committed
# GDS; read here, never recomputed (this check is headless -- no PDK, no
# KLayout).
AUDIT="${EVIDENCE}/area-audit/area-audit.md"

# The one document that must state a current footprint for every block the
# audit records. README.md deliberately carries no block geometry, so the
# completeness half of the footprint rule applies to the proposal only --
# it is the document written to be read by someone outside this repository.
FOOTPRINT_COMPLETE_DOC="docs/chipalooza/challenge-5-proposal.md"

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

# The workflow file that is the single source of truth for which klt
# (klayout-tools) version this repository's committed klt artifacts must have
# been produced on. Read, never restated -- see the ERC RULE below.
CI_WORKFLOW="${REPO_ROOT}/.github/workflows/ci.yml"

# Documents whose prose is checked, relative to the repo root.
DOCS=(
  "README.md"
  "docs/chipalooza/challenge-5-proposal.md"
)

status=0

# The scope rule below needs python3. Absence is a failure, not a quiet
# downgrade to the weaker literal-phrase checks.
have_python=yes
command -v python3 >/dev/null 2>&1 || have_python=no

fail() {
  echo "FAIL: $*" >&2
  status=1
}

# --- Derive the real state from the committed evidence tree ----------------

drawn=0
lvs_matched=0
summary=()
erc_entries=()

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

  # The ERC rule asks for klt erc supply evidence from every block that is
  # LVS-*matched*, using the very verdict derived above rather than a looser
  # "an lvs-clean/ directory exists" test -- a block whose deck said the
  # netlists do not match has a different problem to fix first.
  erc_entries+=("${label}|${dir}|${gds}|${top}|${has_lvs}")
done

# Is there an assembled top level? Nothing in the tree publishes one today;
# when one lands it will be a committed GDS under an evidence directory,
# same as every block above.
top_assembled=no
if compgen -G "${EVIDENCE}/*/pll_top.gds" >/dev/null 2>&1; then
  top_assembled=yes
fi

# The ratification state of spec/pll.md, read from the spec's own Status
# line rather than from anyone's memory of issue #1. Same doctrine as the
# block counts above: derive it, do not restate it.
SPEC="${REPO_ROOT}/spec/pll.md"
spec_status=""
if [ -f "${SPEC}" ]; then
  spec_status="$(grep -m1 -E '^- \*\*Status\*\*:' "${SPEC}" || true)"
fi
spec_ratified=unknown
case "$(printf '%s' "${spec_status}" | tr '[:upper:]' '[:lower:]')" in
*"not yet ratified"* | *"unratified"*) spec_ratified=no ;;
*ratified*) spec_ratified=yes ;;
*proposed*) spec_ratified=no ;;
esac

echo "layout/evidence/ says:"
printf '%s\n' "${summary[@]}"
echo "  assembled pll_top GDS: ${top_assembled}"
echo "spec/pll.md says: ratified=${spec_ratified}"
echo

# --- The ERC rule (see the header) ----------------------------------------
#
# Grades the committed `klt erc` supply evidence against the tree it describes:
# per-block presence, both provenance content hashes, the pinned klt version,
# the spec's top-level schema, and each PROOF-erc.md's own antenna-coverage
# disclosure. Python rather than shell because it reads JSON and needs sha256;
# it still reads only committed files -- no PDK, no KLayout, no klt.
#
# Prints a human summary on stdout and, as its last line, a machine-readable
# "COUNTS <spec> <tie_checked> <supply_clean>" the count rule below consumes.
erc_rule() {
  local evidence="$1" ci_workflow="$2" blocks="$3"
  python3 - "${evidence}" "${ci_workflow}" "${blocks}" <<'PY'
import hashlib
import json
import os
import re
import sys

evidence, ci_workflow, blocks_spec = sys.argv[1], sys.argv[2], sys.argv[3]

failed = False


def fail(msg):
    global failed
    failed = True
    sys.stderr.write("FAIL: %s\n" % msg)


def sha256(path):
    with open(path, "rb") as fh:
        return "sha256:" + hashlib.sha256(fh.read()).hexdigest()


# The klt version CI pins, read from the workflow rather than restated here.
# Absence is a failure: the version claim in every committed report would then
# be gradeable against nothing.
pinned = None
try:
    with open(ci_workflow, encoding="utf-8") as fh:
        m = re.search(r"klayout-tools==([0-9][^'\"\s]*)", fh.read())
        if m:
            pinned = m.group(1)
except OSError as exc:
    fail("cannot read %s: %s" % (ci_workflow, exc))
if pinned is None and not failed:
    fail(
        "%s names no 'klayout-tools==<version>' pin -- the klt version every "
        "committed klt artifact claims cannot be graded against anything"
        % ci_workflow
    )

# `klt erc`'s own documented top-level spec keys (docs/cli/erc.md), plus the
# `_description` this repository puts at the head of each spec. Anything else
# is rejected on purpose: a free-text rationale key is how the stale
# `_ties_omitted` citation survived a fixed upstream bug by five days. Per-entry
# `_comment` annotations are untouched by this rule -- they annotate a
# declaration that exists, rather than standing in for one that does not.
SPEC_KEYS = {
    "_description",
    "stackup",
    "vias",
    "nets",
    "ties",
    "ties_disclosure",
    "devices",
}

# The `ties_disclosure.kind` values klt 0.6.0 recognises. An unrecognised token
# is not a disclosure a grader can act on, so it is not one here either.
DISCLOSURE_KINDS = {"unexpressible", "tool_limitation"}

n_spec = n_tie_checked = n_supply_clean = 0
lines = []

for item in blocks_spec.split(";"):
    if not item:
        continue
    label, directory, gds, top, lvs_matched = item.split("|")
    base = os.path.join(evidence, directory)
    gds_path = os.path.join(base, gds)
    spec_path = os.path.join(base, "erc-supply-spec.json")
    report_path = os.path.join(base, "erc-report.json")
    proof_path = os.path.join(base, "PROOF-erc.md")
    rel = "layout/evidence/%s" % directory

    # An LVS-matched block is one whose supply spec is cheap to produce and
    # therefore owed: item 11's own ERC half needs nothing the LVS run did not
    # already need. The verdict is the one the caller already derived from the
    # deck's own "Netlists match." line -- a block whose netlists do not match
    # has a different problem to fix first, and is not asked for one.
    has_lvs = lvs_matched == "yes"

    present = [
        os.path.isfile(spec_path),
        os.path.isfile(report_path),
        os.path.isfile(proof_path),
    ]
    if not all(present):
        if has_lvs:
            missing = [
                name
                for name, ok in zip(
                    ("erc-supply-spec.json", "erc-report.json", "PROOF-erc.md"),
                    present,
                )
                if not ok
            ]
            fail(
                "%s is LVS-matched but has no complete klt erc "
                "supply evidence: missing %s. T1 item 11's ERC half needs "
                "nothing the LVS run did not already need, so an LVS-clean "
                "block without it is a gap, not a choice."
                % (rel, ", ".join(missing))
            )
        lines.append(
            "  %-20s erc-spec=no  tie=n/a      supply=n/a" % label
        )
        continue

    n_spec += 1

    try:
        with open(spec_path, encoding="utf-8") as fh:
            spec = json.load(fh)
        with open(report_path, encoding="utf-8") as fh:
            report = json.load(fh)
        with open(proof_path, encoding="utf-8") as fh:
            proof_flat = re.sub(r"\s+", " ", fh.read())
    except (OSError, ValueError) as exc:
        fail("%s: cannot read its klt erc evidence: %s" % (rel, exc))
        continue

    # --- Provenance: the report must describe the files committed beside it ---
    prov = report.get("provenance") or {}
    for key, path, what in (
        ("input", gds_path, "the committed GDS"),
        ("spec", spec_path, "the committed supply spec"),
    ):
        stated = (prov.get(key) or {}).get("content_hash")
        actual = sha256(path)
        if stated != actual:
            fail(
                "%s/erc-report.json's provenance.%s.content_hash is %r, but %s "
                "hashes to %r. The report describes a file that is not the one "
                "committed beside it -- re-run `klt erc` (see that block's "
                "PROOF-erc.md for the exact command) rather than editing the "
                "hash." % (rel, key, stated, what, actual)
            )

    if pinned is not None:
        stated_klt = prov.get("klt_version") or ""
        if not stated_klt.startswith(pinned):
            fail(
                "%s/erc-report.json was produced on klt %r, but "
                ".github/workflows/ci.yml pins klayout-tools==%s. A report from "
                "a different klt is not evidence about the klt this repository "
                "grades on." % (rel, stated_klt, pinned)
            )

    # --- The spec's own schema ------------------------------------------------
    stray = sorted(set(spec) - SPEC_KEYS)
    if stray:
        fail(
            "%s/erc-supply-spec.json carries top-level key(s) %s outside `klt "
            "erc`'s documented schema. A free-text rationale key is exactly how "
            "this repository's own `_ties_omitted` note went on citing a "
            "fixed upstream bug: state a deliberate zero-`ties[]` declaration in "
            "the first-class `ties_disclosure` field instead, and put the "
            "narrative in PROOF-erc.md." % (rel, ", ".join(repr(k) for k in stray))
        )

    ties = spec.get("ties") or []
    disclosure = spec.get("ties_disclosure")
    if not ties:
        kind = (disclosure or {}).get("kind")
        if kind not in DISCLOSURE_KINDS:
            fail(
                "%s/erc-supply-spec.json declares no `ties[]` and no usable "
                "`ties_disclosure` (kind %r; klt 0.6.0 recognises %s). An "
                "undisclosed omission and a considered one render identically to "
                "item 11's grader, which is the state this rule exists to "
                "prevent."
                % (rel, kind, " / ".join(sorted(DISCLOSURE_KINDS)))
            )
        if disclosure and not str(disclosure.get("reason", "")).strip():
            fail(
                "%s/erc-supply-spec.json's `ties_disclosure` states no `reason`. "
                "The kind says which obstacle; the reason is what a reader needs "
                "to go fix it." % rel
            )

    # --- Derived coverage, and the antenna disclosure ------------------------
    coverage = report.get("erc_coverage") or {}
    tie_checked = any(
        isinstance(entry, str) and entry.startswith("erc.missing_tie:")
        for entry in coverage.get("checked") or []
    )
    if tie_checked:
        n_tie_checked += 1

    declared = {
        str(entry.get("name", "")).upper()
        for entry in spec.get("nets") or []
        if entry.get("kind") == "supply"
    }
    supply_findings = []
    for finding in report.get("erc_findings") or []:
        rule = finding.get("rule")
        if rule in ("erc.missing_tie", "erc.supply_short"):
            supply_findings.append(rule)
        elif rule in ("erc.unconnected_net", "erc.expected_short_missing"):
            if any(
                str(finding.get(field) or "").upper() in declared
                for field in ("net", "other_net")
            ):
                supply_findings.append(rule)
    if not supply_findings:
        n_supply_clean += 1

    antenna = report.get("coverage") or {}
    n_checked = len(antenna.get("checked") or [])
    n_skipped = len(antenna.get("skipped") or [])
    reasons = sorted(
        {
            str(entry.get("reason"))
            for entry in antenna.get("skipped") or []
            if isinstance(entry, dict)
        }
    )
    claim = "checked: %d, skipped: %d" % (n_checked, n_skipped)
    if claim not in proof_flat:
        fail(
            '%s/PROOF-erc.md does not state "%s" -- its own erc-report.json\'s '
            "antenna coverage. The antenna half of `klt erc` has never run in "
            "this repository, and a record that does not say so lets "
            '"`klt erc` was run" be read as broader than it is.' % (rel, claim)
        )
    for reason in reasons:
        if reason not in proof_flat:
            fail(
                "%s/PROOF-erc.md does not name the skip reason %r its own "
                "erc-report.json records for the antenna half." % (rel, reason)
            )

    lines.append(
        "  %-20s erc-spec=yes tie=%-8s supply=%s"
        % (
            label,
            "checked" if tie_checked else "disclosed",
            "clean" if not supply_findings else "+".join(sorted(set(supply_findings))),
        )
    )

print("layout/evidence/ klt erc supply evidence says:")
for line in lines:
    print(line)
print(
    "  %d of the 4 blocks ERC-checked (supply spec + report + proof, "
    "provenance-verified against the committed GDS); %d with a computed "
    "erc.missing_tie; %d with no supply-side finding"
    % (n_spec, n_tie_checked, n_supply_clean)
)
print("COUNTS %d %d %d" % (n_spec, n_tie_checked, n_supply_clean))
sys.exit(1 if failed else 0)
PY
}

BLOCK_ERC_SPEC=""
for entry in "${erc_entries[@]}"; do
  BLOCK_ERC_SPEC="${BLOCK_ERC_SPEC}${BLOCK_ERC_SPEC:+;}${entry}"
done

erc_spec_count=0
if [ "${have_python}" = yes ]; then
  erc_out="$(erc_rule "${EVIDENCE}" "${CI_WORKFLOW}" "${BLOCK_ERC_SPEC}")" || status=1
  printf '%s\n' "${erc_out}" | grep -v '^COUNTS ' || true
  erc_counts="$(printf '%s\n' "${erc_out}" | grep '^COUNTS ' || true)"
  if [ -n "${erc_counts}" ]; then
    read -r _ erc_spec_count _ _ <<<"${erc_counts}"
  fi
  echo
else
  fail "python3 is not on PATH -- the ERC rule could not run, and a partial pass is not a pass"
fi

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

# Blanket assertions that spec/pll.md is unratified, forbidden once the
# spec's own Status line says otherwise. Note what is deliberately NOT on
# this list: "still unratified", which both documents use correctly for
# DR-007 Amendment A1's two carved-out ROWS. A row-scoped carve-out and a
# blanket "the spec is not ratified" are different claims, and only the
# second one is false.
FORBIDDEN_ONCE_RATIFIED=(
  "pending engineering ratification"
  "pending ratification"
  "not yet ratified"
  "awaiting ratification"
)

# The scope rule (see the header). Implemented in Python rather than in
# grep because it needs a match position and a window around it; python3 is
# already a hard dependency of this repo's headless CI job, which runs
# layout/tests/ next to this script.
#
# SCOPE_TOKENS are the qualifiers that make an absence claim checkable
# against the tree instead of merely absolute. They are only accepted while
# `top_assembled=no`: the day an assembled pll_top lands, every one of them
# becomes a claim that needs re-reading, so the rule stops excusing them
# and forces exactly that re-read.
scope_rule() {
  local doc_path="$1" doc_label="$2" tokens="$3"
  python3 - "${doc_path}" "${doc_label}" "${tokens}" <<'PY'
import re
import sys

path, label, tokens = sys.argv[1], sys.argv[2], sys.argv[3]
scope_tokens = [t for t in tokens.split("|") if t]

with open(path, encoding="utf-8") as fh:
    flat = re.sub(r"\s+", " ", fh.read())
low = flat.lower()

# A negation word, as a whole word, reaching a layout-existence noun within
# the same clause (no sentence-ending "." may intervene, and at most 29
# further characters). "now have a committed block GDS" must not match, so
# the negation needs a non-letter immediately after it; "drawn-band edge"
# must not match, so the noun may not be followed by a letter or a hyphen.
ABSENCE = re.compile(
    r"(?<![a-z-])(?:no|not|never|none|neither|nothing)"
    r"[^a-z.\-][^.]{0,29}(?:layout|gds|drawn)(?![a-z-])"
)

failed = False
for m in ABSENCE.finditer(low):
    start, end = max(0, m.start() - 100), m.end() + 100
    if any(tok in low[start:end] for tok in scope_tokens):
        continue
    failed = True
    sys.stderr.write(
        "FAIL: %s asserts layout does not exist without saying at what "
        'scope: "...%s..."\n'
        "      PLL sub-block layouts are committed under layout/evidence/, "
        "so an unqualified absence claim is false. Name the scope -- the "
        "assembled top level, the extracted post-layout netlist -- within "
        "~100 characters of the negation, or drop the sentence. Accepted "
        "scope words: %s\n" % (label, flat[start:end].strip(), ", ".join(scope_tokens) or "(none)")
    )
sys.exit(1 if failed else 0)
PY
}

# The footprint rule (see the header). Grades stated block geometry against
# layout/evidence/area-audit/area-audit.md instead of against whatever the
# last editor remembered. Like the scope rule it needs match positions, so
# it is Python rather than grep.
#
# BLOCK_SPEC is `<top cell>~<label>;...`: the two names a document may use
# to introduce a block, taken from BLOCKS above so the two lists cannot
# disagree.
BLOCK_SPEC=""
for entry in "${BLOCKS[@]}"; do
  IFS='|' read -r label _dir _gds top <<<"${entry}"
  BLOCK_SPEC="${BLOCK_SPEC}${BLOCK_SPEC:+;}${top}~${label}"
done

footprint_rule() {
  local doc_path="$1" doc_label="$2" audit_path="$3" spec="$4" require_all="$5"
  # Optional 6th arg: an "## <heading>" section name (without the "## ") to
  # scope grading to, so a document that also states unrelated "W x H um"
  # dimensions elsewhere is not misread as making an unattributable footprint
  # claim there. Empty (the default) means the whole document, as before.
  local section="${6:-}"
  python3 - "${doc_path}" "${doc_label}" "${audit_path}" "${spec}" "${require_all}" "${section}" <<'PY'
import re
import sys

doc_path, label, audit_path, spec, require_all, section = sys.argv[1:7]

# --- The tree's own numbers ------------------------------------------------
#
# area-audit.md's first table is one row per block:
#   | `vco_block` | 172.52 x 184.48 | 31,826 | 12,468 | 39.2 % | ... |
# The later tables in the same file start with the same cell but do not
# carry a "W x H" second cell, so this pattern selects the geometry table
# without needing to count tables.
AUDIT_ROW = re.compile(
    r"^\|\s*`([A-Za-z0-9_]+)`\s*\|\s*([0-9]+(?:\.[0-9]+)?)\s*[xX×]\s*"
    r"([0-9]+(?:\.[0-9]+)?)\s*\|\s*([0-9,]+)\s*\|"
)

audit = {}
try:
    with open(audit_path, encoding="utf-8") as fh:
        for line in fh:
            m = AUDIT_ROW.match(line.strip())
            if m and m.group(1) not in audit:
                audit[m.group(1)] = (
                    float(m.group(2)),
                    float(m.group(3)),
                    int(m.group(4).replace(",", "")),
                )
except OSError as exc:  # pragma: no cover - reported by the caller too
    sys.stderr.write("FAIL: cannot read %s: %s\n" % (audit_path, exc))
    sys.exit(1)

if not audit:
    sys.stderr.write(
        "FAIL: %s parsed to zero block rows -- the footprint claims in %s "
        "cannot be graded against anything. Regenerate it with "
        "`python3 layout/run_pv.py area`.\n" % (audit_path, label)
    )
    sys.exit(1)

# --- Where the document names a block --------------------------------------

blocks = []
for item in spec.split(";"):
    if not item:
        continue
    top, name = item.split("~", 1)
    blocks.append((top, name))

with open(doc_path, encoding="utf-8") as fh:
    raw = fh.read()

if section:
    # "## <section>" up to (not including) the next "## " heading, or end of
    # file. re.S so "." spans lines; re.M so "^" anchors each line, matching
    # the section-extraction convention spec/lib/check-spec-row-coverage.sh
    # already uses for spec/pll.md's own tables.
    heading = re.search(
        r"^##\s+" + re.escape(section) + r"\b[^\n]*\n(.*?)(?=^##\s|\Z)",
        raw,
        re.M | re.S,
    )
    if heading is None:
        sys.stderr.write(
            "FAIL: %s has no '## %s' section -- the footprint claims there "
            "cannot be graded\n" % (label, section)
        )
        sys.exit(1)
    raw = heading.group(1)

flat = re.sub(r"\s+", " ", raw)
low = flat.lower()

# (end offset, top cell) for every place a block is introduced by either of
# its names.  The lookarounds keep `vco` inside `vco_block` from counting as
# a separate, nearer mention, and keep a longer identifier from being cut in
# half.
mentions = []
for top, name in blocks:
    for alias in (top, name):
        pat = r"(?<![a-z0-9_])" + r"\s+".join(
            re.escape(w) for w in alias.lower().split()
        ) + r"(?![a-z0-9_])"
        for m in re.finditer(pat, low):
            mentions.append((m.end(), top))
mentions.sort()

# A footprint claim: "W x H um", both dimensions written with a decimal
# point (every real one is, and requiring it keeps integer ratios like
# "3 x 3" out of the rule).
TUPLE = re.compile(
    r"([0-9]+\.[0-9]+)\s*[xX×]\s*([0-9]+\.[0-9]+)\s*(?:µm|um)(?![a-z])"
)
# A mm2 figure sitting directly against a tuple, on either side:
#   "0.0318 mm² (172.52 × 184.48 µm"   /   "172.52 × 184.48 µm (0.0318 mm²)"
PRE_MM2 = re.compile(r"([0-9]+\.[0-9]+)\s*mm²\s*\(\s*$")
POST_MM2 = re.compile(r"^\s*\(\s*([0-9]+\.[0-9]+)\s*mm²")

# How far back a block name may sit and still be the subject of a footprint.
# Section 6's table puts the top cell one cell to the left; section 5's area
# row puts the label a dozen characters back.  160 spans both without
# reaching the previous block's cell.
REACH = 160

failed = False
stated = set()


def fail(msg):
    global failed
    failed = True
    sys.stderr.write("FAIL: %s %s\n" % (label, msg))


for m in TUPLE.finditer(flat):
    w, h = float(m.group(1)), float(m.group(2))
    quoted = flat[max(0, m.start() - 60):m.end() + 40].strip()

    owner = None
    for end, top in mentions:
        if end <= m.start() and m.start() - end <= REACH:
            owner = top
    if owner is None:
        fail(
            'states a footprint that names no block within %d characters of '
            'it: "...%s..." -- a size a reader cannot attribute is not a '
            "checkable claim." % (REACH, quoted)
        )
        continue
    if owner not in audit:
        fail(
            'states a footprint for `%s`, which %s has no row for: "...%s..."'
            % (owner, audit_path, quoted)
        )
        continue

    aw, ah, abbox = audit[owner]
    if (round(w, 2), round(h, 2)) != (round(aw, 2), round(ah, 2)):
        fail(
            "states `%s` at %.2f x %.2f um, but the committed GDS measures "
            '%.2f x %.2f um (%s): "...%s..."'
            % (owner, w, h, aw, ah, audit_path, quoted)
        )
        continue

    stated.add(owner)

    expected_mm2 = "%.4f" % (abbox / 1e6)
    pre = PRE_MM2.search(flat[max(0, m.start() - 40):m.start()])
    post = POST_MM2.search(flat[m.end():m.end() + 40])
    for found in (pre, post):
        if found is None:
            continue
        if "%.4f" % float(found.group(1)) != expected_mm2:
            fail(
                "states `%s` at %s mm2 next to its footprint, but the "
                'committed GDS bbox is %s um2 = %s mm2: "...%s..."'
                % (owner, found.group(1), format(abbox, ","), expected_mm2, quoted)
            )

if require_all == "yes":
    for top, _name in blocks:
        if top in audit and top not in stated:
            aw, ah, abbox = audit[top]
            fail(
                "states no current footprint for `%s`, which %s records at "
                "%.2f x %.2f um (%s um2). Deleting the number is not a way "
                "to stop it being stale."
                % (top, audit_path, aw, ah, format(abbox, ","))
            )

sys.exit(1 if failed else 0)
PY
}

# The count rule (see the header). Grades *every* occurrence of a "N of the
# 4 ..." claim in a document, not just whether the correct one is present
# somewhere -- the gap that let a stale duplicate survive in the very commit
# that fixed the sentence next to it.
count_rule() {
  local doc_path="$1" doc_label="$2" drawn="$3" lvs_matched="$4" erc_checked="$5"
  python3 - "${doc_path}" "${doc_label}" "${drawn}" "${lvs_matched}" "${erc_checked}" <<'PY'
import re
import sys

doc_path, label = sys.argv[1], sys.argv[2]
drawn, lvs_matched, erc_checked = (int(v) for v in sys.argv[3:6])

with open(doc_path, encoding="utf-8") as fh:
    flat = re.sub(r"\s+", " ", fh.read())
low = flat.lower()

failed = False


def check(pattern, expected, what):
    global failed
    for m in re.finditer(pattern, low):
        stated = int(m.group(1))
        if stated == expected:
            continue
        failed = True
        quoted = flat[max(0, m.start() - 40):m.end() + 40].strip()
        sys.stderr.write(
            'FAIL: %s states "%s of the 4 %s", but layout/evidence/ records '
            '%s of the 4: "...%s..."\n' % (label, stated, what, expected, quoted)
        )


# "N of the 4 [PLL] sub-blocks" -- the drawn+DRC-clean count.
check(r"([0-9]+)\s+of the 4\s+(?:pll\s+)?sub-blocks", drawn, "sub-blocks drawn and DRC-clean")
# "N of the 4 [are] LVS-matched" -- the LVS-matched count.
check(r"([0-9]+)\s+of the 4\s+(?:are\s+)?lvs-matched", lvs_matched, "LVS-matched")
# "N of the 4 [blocks] [are] ERC-checked" -- the klt erc supply-evidence count
# (issue #565). Graded only where a document chooses to state it: no document
# has to carry this claim, but one that does may not carry a stale one. This is
# the drift the ERC RULE's own derived count exists to make checkable -- four
# separate #127 passes re-derived "1 of 4 blocks ERC-checked" by hand.
check(
    r"([0-9]+)\s+of the 4\s+(?:pll\s+)?(?:sub-)?blocks?\s+(?:are\s+)?erc-checked",
    erc_checked,
    "blocks ERC-checked",
)
check(r"([0-9]+)\s+of the 4\s+(?:are\s+)?erc-checked", erc_checked, "blocks ERC-checked")

sys.exit(1 if failed else 0)
PY
}

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

    # The mechanism the list above is no longer trusted to be. A missing
    # python3 is reported as a failure after the loop rather than silently
    # running this check with its main rule switched off.
    if [ "${have_python}" = yes ]; then
      if [ "${top_assembled}" = no ]; then
        scope_tokens="top level|top-level|pll_top|assembled|post-layout|extracted|parasitic|placed-and-routed"
      else
        scope_tokens=""
      fi
      scope_rule "${path}" "${doc}" "${scope_tokens}" || status=1
      count_rule "${path}" "${doc}" "${drawn}" "${lvs_matched}" "${erc_spec_count}" || status=1

      if [ -f "${AUDIT}" ]; then
        require_all=no
        [ "${doc}" = "${FOOTPRINT_COMPLETE_DOC}" ] && require_all=yes
        footprint_rule "${path}" "${doc}" "${AUDIT}" "${BLOCK_SPEC}" "${require_all}" || status=1
      fi
    fi
  fi

  if [ "${spec_ratified}" = yes ]; then
    for phrase in "${FORBIDDEN_ONCE_RATIFIED[@]}"; do
      if printf '%s' "${flat}" | grep -qiF "${phrase}"; then
        fail "${doc} says \"${phrase}\", but spec/pll.md's own Status line reads: ${spec_status#- }"
      fi
    done
  fi
done

# The fifth guard (see the header): spec/pll.md's own "## Area" section
# states the same four block footprints, and nothing above touches it -- the
# DOCS loop's other rules (scope, count, forbidden phrases) do not fit a
# normative spec the way they fit a status narrative. Scoped to that one
# section, not the whole file, so the loop filter's unrelated device
# dimensions elsewhere in the document are not misread as a footprint claim.
if [ "${drawn}" -gt 0 ] && [ "${have_python}" = yes ] && [ -f "${AUDIT}" ] && [ -f "${SPEC}" ]; then
  footprint_rule "${SPEC}" "spec/pll.md" "${AUDIT}" "${BLOCK_SPEC}" yes Area || status=1
fi

if [ "${have_python}" = no ] && [ "${drawn}" -gt 0 ]; then
  fail "python3 is not on PATH -- the scope rule (the main prose check here) could not run, and a partial pass is not a pass"
fi

# Same doctrine as the missing-spec-Status failure below: a guard whose
# input has gone missing reports that, rather than passing on the checks it
# can still run. Blocks are drawn, so the audit that measures them must
# exist -- regenerate it with `python3 layout/run_pv.py area`.
if [ "${drawn}" -gt 0 ] && [ ! -f "${AUDIT}" ]; then
  fail "layout/evidence/area-audit/area-audit.md is missing -- ${drawn} block layout(s) are committed, so the footprint claims in both documents cannot be graded against anything"
fi

if [ "${spec_ratified}" = unknown ]; then
  fail "could not read a '- **Status**:' line from spec/pll.md -- the ratification claims in the documents above cannot be graded against anything"
fi

if [ "${status}" -eq 0 ]; then
  echo "OK: README.md and docs/chipalooza/challenge-5-proposal.md match layout/evidence/" \
    "(${drawn}/4 drawn + DRC-clean, ${lvs_matched}/4 LVS-matched, ${erc_spec_count}/4 ERC-checked," \
    "assembled pll_top: ${top_assembled})" \
    "and spec/pll.md (ratified: ${spec_ratified}); no unscoped absence-of-layout claim;" \
    "every stated block footprint matches layout/evidence/area-audit/area-audit.md," \
    "including spec/pll.md's own '## Area' section;" \
    "every committed klt erc report's provenance matches the GDS and spec beside it," \
    "on the klt version .github/workflows/ci.yml pins"
fi

exit "${status}"
