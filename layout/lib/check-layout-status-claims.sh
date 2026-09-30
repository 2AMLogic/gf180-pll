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
# The scope rule grades *negated* absence claims, and on 2026-09-28 a claim
# escaped it by not using a negation. Section 8's "Flow" bullet -- the one
# paragraph an outside reviewer reads to decide whether this project's layout
# toolchain is credible -- said "layout, DRC, and LVS (once drawn) via
# KLayout ... proven on the inverter test cell referenced in section 6",
# while section 6 three pages earlier recorded four transistor-level blocks
# DRC-clean and LVS-matched against the PDK's own foundry signoff decks. A
# *deferral* ("once drawn", "when laid out") asserts exactly what a negation
# asserts -- that the thing does not exist yet -- so the scope rule now has a
# DEFERRAL half beside its ABSENCE half, excused by the same scope tokens.
# It is the third time the same document has understated its own layout tree
# in a sibling sentence the then-current mechanism could not see, which is
# why the fix is a rule rather than a fourth remembered phrase.
#
# A bare deferral is what fails. One that names its subject -- "when the loop
# filter is drawn", which this repository says truthfully and repeatedly --
# does not, because naming the subject is what makes the claim checkable.
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
#   * the report's `provenance.klt_version` must equal the klt version
#     `.github/workflows/ci.yml` pins, read from that file rather than restated
#     here. **Equal, not merely start with** -- tightened 2026-09-28 (issue
#     #127) after the prefix form let every one of the four committed reports
#     claim the pinned `0.6.0` while actually recording `0.6.0+gf2d249ab23d4`,
#     a post-tag source build whose `klt erc` JSON carried a `nets[]`
#     supply-continuity block the released wheel does not emit, at an
#     unchanged `schema_version`. That is the same failure this rule was
#     created for (a `0.5.0` report under a `0.6.0` pin), one release apart and
#     invisible to a prefix test;
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
# A seventh guard, the KLAYOUT PIN RULE, added 2026-09-28 (issue #127), applies
# the ERC RULE's own doctrine to the other engine this repository's evidence
# comes out of. The ERC rule grades `klt`'s version because a report from an
# unpinned klt is not evidence about the klt this repo grades on. Exactly the
# same is true of the KLayout application binary that runs the foundry DRC and
# LVS decks -- and nothing checked it. `layout/harness/env.py` has carried
# `KNOWN_GOOD_KLAYOUT_VERSION = "KLayout 0.28.16"` since bring-up, with a
# documented reason that is not cosmetic (issue #360: a newer KLayout has been
# observed to report a *false* LVS mismatch on an unchanged, LVS-clean layout),
# but that constant only ever produced an advisory WARNING at run time, about
# the binary you are about to use. It said nothing about the logs already
# committed. A census run for issue #127 found **16 of the 51** committed
# DRC/LVS deck logs were captured on KLayout 0.30.9 or 0.30.10, not on the pin
# -- including `vco_block`'s own block-level DRC-clean and LVS-match logs, the
# two artifacts T1 items 3 and 4 score the VCO on. Both `layout/README.md` and
# issue #127's own body meanwhile asserted that every committed DRC/LVS
# artifact was produced on 0.28.16. So:
#
#   * every block that reads as drawn must have at least one committed DRC log
#     for its own top cell, recorded on the pinned KLayout, carrying the deck's
#     own `Klayout DRC run is clean.` verdict; and every block that reads as
#     LVS-matched must likewise have at least one on-pin log carrying
#     `Congratulations! Netlists match.`. "At least one", not "all", on purpose:
#     `sim/`-style append-only evidence means a superseded off-pin run stays in
#     the tree beside the on-pin one that re-derived it, and deleting it to
#     satisfy a checker would be the wrong repair;
#   * the pin itself is read out of `layout/harness/env.py`, never restated
#     here -- same doctrine as the klt pin being read out of the CI workflow;
#   * and every remaining off-pin log must be named in OFF_PIN_DISCLOSED below
#     with a reason. A new off-pin log fails the build. This is what makes
#     "16 of 51 are off-pin" a number this script prints rather than a sentence
#     someone re-derives by hand. The converse -- a disclosure entry whose file
#     has since disappeared -- is asserted against the real tree by
#     layout/tests/test_layout_status_claims.py rather than here, because this
#     rule must stay correct on the synthetic trees its own unit tests drive it
#     against, which hold none of those files.
#
# The rule above grades the **four block top cells** only, and that is where it
# left a residual it disclosed rather than closed: the five VCO *sub-cell* logs
# (`vco_ring`, `vco_vtoi_core`, `vco_out_buffer`) stayed on 0.30.9/0.30.10, and
# two of them (`lvs-ring`, `lvs-buffer`) had additionally been run at
# `POLY_RES 1k` rather than this repository's ratified `3k` (DR-009). A
# disclosure entry is not a check: it says the gap exists, and then grades
# nothing about whether it ever closes or silently widens. So the rule is
# generalised (issue #127, 2026-09-30) from four named tops to **every** top
# cell the evidence tree grades:
#
#   * every top cell for which some committed log carries the deck's own
#     `Klayout DRC run is clean.` must have at least one such log on the pin,
#     and the same for `Congratulations! Netlists match.` -- not just the four
#     block tops. A sub-cell verdict is the warrant under a block verdict; a
#     warrant taken on an engine this repository does not grade on is exactly
#     the shape issue #360 makes dangerous;
#   * a top cell whose verdicts are *deliberately* not graded on the pin must
#     be named in OFF_PIN_TOPCELL_DISCLOSED below with a reason -- a cell-level
#     exemption, distinct from OFF_PIN_DISCLOSED's per-file one. Three families
#     qualify today and all three predate this rule: the two `cp_leg_*`
#     leaf-cell generator proofs and `inv_tb`, the DRC/LVS harness's own
#     bring-up proof (with its two deliberate fault negative controls), none of
#     which is a PLL block or the warrant under one.
#
# An eighth guard, the PIN RESTATEMENT RULE, added 2026-09-28 (issue #237),
# closes the prose half of the rule above. The KLAYOUT PIN RULE grades the
# *logs* against `layout/harness/env.py`; nothing graded what the documents
# say the pin is, or what they say it guarantees -- and that is precisely
# where the failure #127 found actually lived. `layout/README.md` asserted
# for about five weeks that "the committed DRC/LVS evidence under
# `layout/evidence/*/` was captured against KLayout 0.28.16" while 16 of the
# 51 committed deck logs were not; the same sentence was live in
# `layout/harness/env.py`'s own runtime WARNING, printed to every user of
# `run_pv.py check-env|drc|lvs`; and §8 of the Chipalooza proposal attributed
# the pin of "every committed layout artifact" to `.github/workflows/ci.yml`,
# which pins `klt`, not the KLayout application binary that runs the decks.
# Two engines, two pins, two source files -- stated as one. So:
#
#   * every version a graded document states *as this repository's pin* must
#     equal `KNOWN_GOOD_KLAYOUT_VERSION`, read from `layout/harness/env.py`.
#     Bumping the pin now fails the build until the prose follows it;
#   * and the proposal -- the document written to be read from outside this
#     repository, whose §6 table is the DRC/LVS claim a reviewer scores --
#     must state the pin at least once. A verdict table that never names the
#     engine it was produced on is not checkable by its reader.
#
# Deliberately narrow: it grades the `pins X` / `pinned at X` / "the `X` pin"
# shapes, and NOT "captured against X". Both documents quote the superseded
# "captured against" sentence on purpose, as history -- and a check that
# grades a claim cannot tell asserting it from quoting it (the same tension
# the footprint rule's own header records). The shape that asserts a pin is
# graded; the shape that narrates one that was wrong is left quotable.
#
# A ninth guard, the LAYER CENSUS RULE, added 2026-09-29 (issue #663), grades
# the one class of claim in this repository's evidence that is printed as raw
# tool output and was therefore trusted as if it could not be wrong. Several
# `PROOF-erc.md` records justify what their `erc-supply-spec.json` declares --
# and, more importantly, what it deliberately does NOT declare (a `label_layer`
# on a metal that carries no supply text, a `well_layer` for a native
# p-substrate) -- by enumerating the committed GDS's own `layer_indexes()` as a
# `{layer/datatype, ...}` set. Nothing checked those sets. Issue #660 found
# `layout/evidence/vco-layout/PROOF-erc.md` stating a 14-member census of a
# file that has 15: `(0, 0)`, the two 22 pF decap marker rectangles' layer, was
# simply missing from a hand-transcribed list, and the same document quoted the
# correct 15-member list three sections later, so it disagreed with itself.
# Issue #661 then found the identical wrong list copied into that block's
# `erc-supply-spec.json` `_comment`. That is two documents wrong for five weeks
# about a fact `python3 -c "import klayout.db"` answers in a second.
#
# So this rule reads the committed GDS. **That is a deliberate change to this
# script's contract** and it is worth stating plainly, because every guard
# above advertises the opposite: this check used to read only committed text
# files. It still needs no PDK and no standalone KLayout application binary --
# what it now needs is `klayout.db`, the `klayout` pip wheel's Python module
# (layout/README.md, "The two KLayouts", distinguishes the two), which
# `.github/workflows/ci.yml` already installs earlier in this very job for
# layout/tests/. A census claim is a claim about a binary artifact; there is no
# way to grade it from text alone, and leaving it ungraded is what issue #660
# actually cost. The dependency is demanded lazily -- only when a document
# makes a census claim -- so this rule adds nothing to a tree that makes none,
# but where a claim exists a missing `klayout.db` is a FAILURE and not a skip,
# for the same reason a missing python3 is above: a partial pass is not a pass.
#
#   * every `{d/d, d/d, ...}` brace-list in `layout/evidence/*/PROOF-*.md` that
#     is presented as a `layer_indexes()` result must equal, as a set, the
#     layer/datatype pairs the GDS it names actually contains;
#   * which GDS it names is resolved rather than assumed: the block's own GDS
#     by default, or an explicitly named sibling in the same evidence directory
#     (`vco_bandsel_mirror.gds` and friends -- vco-layout alone commits six
#     GDS files) when the sentence names one. A census in a directory where
#     neither rule resolves a file fails, asking the writer to name it, rather
#     than being silently skipped;
#   * and an occurrence inside `~~...~~` is skipped. This repository corrects
#     evidence by striking the wrong value and stating the right one beside it
#     -- #660's own fix left the wrong 14-member list in place, struck -- so a
#     grader that could not tell asserting from quoting would fail the document
#     the moment it was corrected, which is precisely backwards. Same tension
#     the PIN RESTATEMENT RULE above records; there the shape of the sentence
#     resolves it, here the strike-through markup does, because a struck census
#     and a live one are the same shape by construction.
#
# Its own unit tests drive it against synthetic trees carrying generated GDS
# fixtures (`layout/tests/test_layout_status_claims.py`), not against the real
# evidence tree -- same doctrine as the KLAYOUT PIN RULE's: a rule that is only
# ever run where it passes proves nothing about what it would catch.
#
# Usage: layout/lib/check-layout-status-claims.sh
# Exit codes: 0 all claims match the tree, 1 any mismatch.
#
# Dependencies: python3 (hard), and `klayout.db` (the `klayout` pip wheel) when
# any graded document states a `layer_indexes()` census. No PDK, no xschem, no
# standalone KLayout application binary, ever.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EVIDENCE="${REPO_ROOT}/layout/evidence"

# The machine-generated block-geometry audit the footprint rule grades
# against. Regenerated by `python3 layout/run_pv.py area` from the committed
# GDS; read here, never recomputed (this check is headless -- no PDK, and no
# standalone KLayout application binary. The LAYER CENSUS RULE does read the
# committed GDS through `klayout.db`, the pip wheel's Python module; nothing
# here runs a deck or measures geometry.)
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

# The module that is the single source of truth for which KLayout application
# binary this repository's committed DRC/LVS deck logs must have been produced
# on (`KNOWN_GOOD_KLAYOUT_VERSION`). Read, never restated -- see the KLAYOUT
# PIN RULE below.
HARNESS_ENV="${REPO_ROOT}/layout/harness/env.py"

# Documents whose prose is checked, relative to the repo root.
DOCS=(
  "README.md"
  "docs/chipalooza/challenge-5-proposal.md"
)

# Documents the PIN RESTATEMENT RULE grades, relative to the repo root. A
# separate list from DOCS on purpose: layout/README.md is the flow's own
# operator manual, not a status narrative, so the DOCS loop's drawn/LVS-count,
# scope and footprint rules do not fit it -- but it is where this repository's
# KLayout pin is explained, and where the claim the pin rule exists to end
# lived for five weeks.
PIN_DOCS=(
  "README.md"
  "docs/chipalooza/challenge-5-proposal.md"
  "layout/README.md"
)

# The one document that must state the KLayout pin, not merely avoid stating
# it wrongly. Same reasoning as FOOTPRINT_COMPLETE_DOC above: it is the
# document written to be read by someone outside this repository, and §6's
# DRC/LVS verdicts are only evidence about the engine that produced them.
PIN_STATED_DOC="docs/chipalooza/challenge-5-proposal.md"

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
pin_entries=()

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

  # The KLAYOUT PIN RULE asks the same two verdicts be reproducible on the
  # pinned KLayout, so it needs both halves of the derivation above, not just
  # the LVS one: a block that reads drawn owes an on-pin DRC log, and a block
  # that reads LVS-matched owes an on-pin LVS log.
  pin_entries+=("${label}|${top}|${has_drc}|${has_lvs}")
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
        # Exact equality, not a prefix match. The first version of this rule
        # asked `stated_klt.startswith(pinned)`, and that is precisely how a
        # source build got past it for three weeks: all four committed reports
        # recorded `0.6.0+gf2d249ab23d4`, which starts with the pinned `0.6.0`
        # but is a PEP 440 *local version* -- a build of the tree after the
        # v0.6.0 tag, not the released wheel `pip install
        # 'klayout-tools==0.6.0'` installs. signoff/README.md already documents
        # that exact discriminator ("A source build reports a PEP 440
        # local-version suffix ... where the released wheel reports exactly
        # `klt 0.6.0`") and the distinction is not cosmetic: the post-tag build
        # emitted a top-level `nets[]` supply-continuity block, and an
        # `erc_coverage.layers_in_stream_without_declaration` key, that the
        # release does not emit at all -- with `schema_version` unchanged at 1
        # in both, so nothing else in the envelope could have caught it.
        if stated_klt != pinned:
            fail(
                "%s/erc-report.json was produced on klt %r, but "
                ".github/workflows/ci.yml pins klayout-tools==%s. A report from "
                "a different klt is not evidence about the klt this repository "
                "grades on -- and a %r-style local-version suffix means a "
                "source build of the tree *after* that tag, whose JSON field "
                "set can differ from the released wheel's without any "
                "schema_version change to announce it. Re-run `klt erc` on the "
                "pinned release (see that block's PROOF-erc.md for the exact "
                "command) rather than editing the version string."
                % (rel, stated_klt, pinned, pinned + "+g<sha>")
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

# --- The KLayout pin rule (see the header) ---------------------------------
#
# Grades the *engine* every committed DRC/LVS deck log was produced on against
# the pin `layout/harness/env.py` declares, and requires each block's own
# scored verdict to exist on that pin. Reads only committed files -- no PDK,
# no KLayout.
klayout_pin_rule() {
  local evidence="$1" harness_env="$2" blocks="$3"
  python3 - "${evidence}" "${harness_env}" "${blocks}" <<'PY'
import os
import re
import sys

evidence, harness_env, blocks_spec = sys.argv[1], sys.argv[2], sys.argv[3]

failed = False


def fail(msg):
    global failed
    failed = True
    sys.stderr.write("FAIL: %s\n" % msg)


# Off-pin logs that are committed on purpose, each with the reason it is not a
# defect. Paths are relative to layout/evidence/. Every entry is asserted to
# exist, so a stale one fails rather than quietly widening the exemption.
#
# The rule for adding to this list: a log belongs here when it is NOT one of
# the block-level DRC/LVS verdicts T1 items 3 and 4 score, or when being
# off-pin is the whole point of the run. Anything else must be re-run on the
# pin instead of listed.
OFF_PIN_DISCLOSED = {
    # Deliberately off-pin: this IS the cross-version re-check. PR #471 re-ran
    # lock_detector's LVS on a second KLayout to show the match does not depend
    # on the pinned build; listing it as an exception is the point of it.
    "lock-detector-layout/lvs-recheck-klayout-0.30.10/lvs.stdout.log":
        "deliberate cross-version re-check (issue #440 / PR #471)",
    # Leaf-cell generator proofs, not block-level evidence for items 3/4. They
    # prove a generator; the blocks that instantiate them are graded on their
    # own on-pin block-level runs.
    "cp-leg-proof/drc-clean/cp_leg_n.drc.stdout.log": "leaf-cell generator proof",
    "cp-leg-proof/drc-clean/cp_leg_p.drc.stdout.log": "leaf-cell generator proof",
    "cp-leg-proof/lvs-clean/cp_leg_n.lvs.stdout.log": "leaf-cell generator proof",
    "cp-leg-proof/lvs-clean/cp_leg_p.lvs.stdout.log": "leaf-cell generator proof",
    # The DRC/LVS harness's own bring-up proof, including its two deliberate
    # fault negative controls. Not a PLL block at all.
    "inv-tb-proof/drc-clean/drc.stdout.log": "harness bring-up proof (not a PLL block)",
    "inv-tb-proof/drc-fault/drc.stdout.log": "harness bring-up proof, negative control",
    "inv-tb-proof/lvs-clean/lvs.stdout.log": "harness bring-up proof (not a PLL block)",
    "inv-tb-proof/lvs-fault/lvs.stdout.log": "harness bring-up proof, negative control",
    # vco_block's original block-level runs, captured on 0.30.10. Kept per this
    # repository's append-only evidence convention; superseded for grading
    # purposes by drc-recheck-klayout-0.28.16/ and lvs-recheck-klayout-0.28.16/,
    # which re-derived both verdicts on the pin from the same committed GDS and
    # the same committed reference netlist (issue #127, PROOF-klayout-pin.md).
    "vco-layout/drc-clean/drc-block.stdout.log":
        "superseded on the pin by drc-recheck-klayout-0.28.16/",
    "vco-layout/lvs-clean/lvs.stdout.log":
        "superseded on the pin by lvs-recheck-klayout-0.28.16/",
    # VCO sub-cell runs, captured on 0.30.9/0.30.10 (and, for the two LVS
    # logs, at the PDK runner's own POLY_RES 1k rather than this repo's
    # ratified 3k). These were issue #127's disclosed off-pin residual until
    # 2026-09-30, when each was re-derived on the pin at POLY_RES 3k from the
    # same committed GDS and, for LVS, the same committed reference netlist.
    # Kept per this repository's append-only evidence convention; superseded
    # for grading purposes by the sibling recheck directories named below
    # (PROOF-klayout-pin.md, Addendum 1).
    "vco-layout/drc-clean/drc.stdout.log":
        "vco_ring sub-cell, superseded on the pin by drc-recheck-klayout-0.28.16/drc-ring.stdout.log",
    "vco-layout/drc-clean/drc-buffer.stdout.log":
        "vco_out_buffer sub-cell, superseded on the pin by drc-recheck-klayout-0.28.16/drc-buffer.stdout.log",
    "vco-layout/drc-clean/drc-vtoi-core.stdout.log":
        "vco_vtoi_core sub-cell, superseded on the pin by drc-recheck-klayout-0.28.16/drc-vtoi-core.stdout.log",
    "vco-layout/lvs-ring/lvs.stdout.log":
        "vco_ring sub-cell at POLY_RES 1k, superseded on the pin at 3k by lvs-recheck-klayout-0.28.16/lvs-ring.stdout.log",
    "vco-layout/lvs-buffer/lvs.stdout.log":
        "vco_out_buffer sub-cell at POLY_RES 1k, superseded on the pin at 3k by lvs-recheck-klayout-0.28.16/lvs-buffer.stdout.log",
}

# Cell-level counterpart to OFF_PIN_DISCLOSED: top cells whose graded verdicts
# are deliberately not reproduced on the pin at all. Distinct from the per-file
# list above, which excuses one superseded *log* while the cell itself is still
# required to have an on-pin verdict somewhere in the tree. Nothing that is a
# PLL block, or the warrant under a PLL block's own verdict, belongs here.
OFF_PIN_TOPCELL_DISCLOSED = {
    "cp_leg_n": "leaf-cell generator proof, not a block verdict or its warrant",
    "cp_leg_p": "leaf-cell generator proof, not a block verdict or its warrant",
    "inv_tb": "DRC/LVS harness bring-up proof (not a PLL block), incl. its fault controls",
}

DRC_CLEAN = "Klayout DRC run is clean."
LVS_MATCH = "Congratulations! Netlists match."

# The pin, read out of layout/harness/env.py rather than restated here.
# Absence is a failure: every committed log's engine claim would then be
# gradeable against nothing, which is the state this rule exists to end.
pin = None
try:
    with open(harness_env, encoding="utf-8") as fh:
        m = re.search(
            r'^KNOWN_GOOD_KLAYOUT_VERSION\s*=\s*"([^"]+)"', fh.read(), re.M
        )
        if m:
            pin = m.group(1)
except OSError as exc:
    fail("cannot read %s: %s" % (harness_env, exc))
if pin is None and not failed:
    fail(
        "%s declares no KNOWN_GOOD_KLAYOUT_VERSION -- the KLayout every "
        "committed DRC/LVS log was produced on cannot be graded against "
        "anything" % harness_env
    )

VERSION_RE = re.compile(r"Your Klayout version is: (KLayout [0-9][0-9.]*)")
CELL_RE = re.compile(r"on cell ([A-Za-z0-9_]+)")

logs = []
for dirpath, _dirnames, filenames in os.walk(evidence):
    for name in sorted(filenames):
        if not name.endswith(".log"):
            continue
        path = os.path.join(dirpath, name)
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        found = VERSION_RE.search(text)
        if not found:
            continue
        cell = CELL_RE.search(text)
        logs.append(
            {
                "rel": os.path.relpath(path, evidence),
                "version": found.group(1),
                "cell": cell.group(1) if cell else "",
                "drc_clean": DRC_CLEAN in text,
                "lvs_match": LVS_MATCH in text,
            }
        )

on_pin = [entry for entry in logs if pin is not None and entry["version"] == pin]
off_pin = [entry for entry in logs if pin is not None and entry["version"] != pin]

for entry in sorted(off_pin, key=lambda e: e["rel"]):
    if entry["rel"] not in OFF_PIN_DISCLOSED:
        fail(
            "layout/evidence/%s was produced on %s, but layout/harness/env.py "
            "pins %s. A deck log from a different KLayout is not evidence "
            "about the KLayout this repository grades on -- issue #360 records "
            "a newer build reporting a FALSE LVS mismatch on an unchanged, "
            "LVS-clean layout. Re-run it on the pin (see that block's PROOF "
            "for the exact command), or, if being off-pin is the point of the "
            "run, add it to OFF_PIN_DISCLOSED in this script with the reason."
            % (entry["rel"], entry["version"], pin)
        )

# A disclosure list that outlives its files stops being a disclosure and
# becomes a blanket excuse, so the entries are asserted to exist too -- but in
# `layout/tests/test_layout_status_claims.py`
# (`test_the_off_pin_disclosure_list_has_no_stale_entries`), against the real
# tree, not here. This rule has to stay correct on a synthetic tree that holds
# none of these files, which is the only kind of tree its own unit tests can
# drive it against.

for item in blocks_spec.split(";"):
    if not item:
        continue
    label, top, has_drc, has_lvs = item.split("|")
    for want, flag, needle, what in (
        ("drc_clean", has_drc, DRC_CLEAN, "DRC-clean"),
        ("lvs_match", has_lvs, LVS_MATCH, "LVS-match"),
    ):
        if flag != "yes":
            continue
        if not any(e["cell"] == top and e[want] for e in on_pin):
            fail(
                "%s reads as %s from the evidence tree, but no committed deck "
                "log for top cell `%s` carries that verdict on %s -- every "
                "such log is from some other KLayout build. T1 items 3 and 4 "
                "score this verdict; it has to be reproducible on the engine "
                "this repository pins." % (label, what, top, pin)
            )

# The same rule, generalised past the four block tops to every top cell the
# evidence tree grades (see the header). A sub-cell verdict is the warrant
# under a block verdict, and a warrant taken on an unpinned engine is the
# shape issue #360 makes dangerous.
graded_tops = {}
for entry in logs:
    if not entry["cell"]:
        continue
    for want, needle_name in (("drc_clean", "DRC-clean"), ("lvs_match", "LVS-match")):
        if entry[want]:
            graded_tops.setdefault((entry["cell"], needle_name), []).append(entry)
for (top, what), entries in sorted(graded_tops.items()):
    if top in OFF_PIN_TOPCELL_DISCLOSED:
        continue
    if any(e["version"] == pin for e in entries):
        continue
    fail(
        "top cell `%s` carries a %s verdict in %d committed deck log(s), but "
        "not one of them is on %s -- every one is from some other KLayout "
        "build. Re-run it on the pin (see that cell's PROOF for the exact "
        "command), or, if this cell's verdicts are deliberately not graded on "
        "the pin, name it in OFF_PIN_TOPCELL_DISCLOSED in this script with the "
        "reason. Disclosing the individual logs in OFF_PIN_DISCLOSED is not "
        "enough: that excuses a superseded run, not an ungraded cell."
        % (top, what, len(entries), pin)
    )

print("layout/evidence/ DRC/LVS deck logs say:")
print(
    "  %d deck logs carry a KLayout version stamp; %d on the pin (%s), "
    "%d off-pin"
    % (len(logs), len(on_pin), pin, len(off_pin))
)
for entry in sorted(off_pin, key=lambda e: e["rel"]):
    print(
        "  off-pin  %-16s %-56s (%s)"
        % (entry["version"], entry["rel"], OFF_PIN_DISCLOSED.get(entry["rel"], "UNDISCLOSED"))
    )
graded_cells = sorted({top for top, _what in graded_tops})
exempt_cells = [c for c in graded_cells if c in OFF_PIN_TOPCELL_DISCLOSED]
print(
    "  %d graded top cell(s); %d with every stated verdict reproduced on the "
    "pin, %d deliberately exempt (%s)"
    % (
        len(graded_cells),
        len(graded_cells) - len(exempt_cells),
        len(exempt_cells),
        ", ".join(exempt_cells) or "none",
    )
)
sys.exit(1 if failed else 0)
PY
}

# --- The pin restatement rule (see the header) ----------------------------
#
# Grades what the *documents* say this repository's KLayout pin is, against
# what `layout/harness/env.py` declares it to be. The rule above grades the
# logs; this one grades the prose about them.
pin_restatement_rule() {
  local harness_env="$1" pin_stated_doc="$2"
  shift 2
  python3 - "${harness_env}" "${pin_stated_doc}" "$@" <<'PY'
import os
import re
import sys

harness_env, pin_stated_doc = sys.argv[1], sys.argv[2]
doc_args = sys.argv[3:]

failed = False


def fail(msg):
    global failed
    failed = True
    sys.stderr.write("FAIL: %s\n" % msg)


# The pin, read out of layout/harness/env.py rather than restated here --
# the whole point of this rule is that exactly one file gets to say it.
pin = None
try:
    with open(harness_env, encoding="utf-8") as fh:
        m = re.search(r'^KNOWN_GOOD_KLAYOUT_VERSION\s*=\s*"([^"]+)"', fh.read(), re.M)
        if m:
            pin = m.group(1)
except OSError as exc:
    fail("cannot read %s: %s" % (harness_env, exc))
if pin is None:
    if not failed:
        fail(
            "%s declares no KNOWN_GOOD_KLAYOUT_VERSION -- the pin the "
            "documents restate cannot be graded against anything" % harness_env
        )
    sys.exit(1)

# The numeric tail of the pin ("0.28.16" out of "KLayout 0.28.16"), for the
# bare-version shape below.
pin_number = pin.split()[-1]

# The two shapes that *assert* a pin. "captured against X" is deliberately
# absent -- see this script's header for why that one stays quotable.
#
#   "pins `KLayout 0.28.16`", "pinned at `KLayout 0.28.16`", "pin: KLayout X"
FULL_PIN_RE = re.compile(
    r"pin(?:s|ned)?\s*(?:at|to|:)?\s*[`'\"(]*\s*(KLayout\s+[0-9][0-9.]*)", re.I
)
#   "the `0.28.16` pin" -- the same assertion with the program name elided.
BARE_PIN_RE = re.compile(r"[`'\"]?\b([0-9]+\.[0-9]+\.[0-9]+)\b[`'\"]?\s+pin\b", re.I)

stated_in_required_doc = False

for arg in doc_args:
    label, path = arg.split("=", 1)
    if not os.path.exists(path):
        # Silently skipped, not failed. Two of these three files are already
        # in DOCS, whose loop reports their absence; and that PIN_DOCS all
        # exist in the real tree is asserted by
        # layout/tests/test_layout_status_claims.py against the real tree --
        # same doctrine as the off-pin disclosure list, and for the same
        # reason: this rule must stay correct on the synthetic trees its own
        # unit tests drive it against.
        continue
    with open(path, encoding="utf-8") as fh:
        flat = re.sub(r"\s+", " ", fh.read())

    for found in FULL_PIN_RE.finditer(flat):
        stated = re.sub(r"\s+", " ", found.group(1))
        if stated == pin:
            if label == pin_stated_doc:
                stated_in_required_doc = True
            continue
        quoted = flat[max(0, found.start() - 60):found.end() + 60].strip()
        fail(
            '%s states `%s` as this repository\'s KLayout pin, but '
            "layout/harness/env.py declares `%s`. The pin is read from that "
            "one file, never restated -- a document that names a different "
            'engine is describing evidence this tree does not hold: "...%s..."'
            % (label, stated, pin, quoted)
        )

    for found in BARE_PIN_RE.finditer(flat):
        if found.group(1) == pin_number:
            continue
        quoted = flat[max(0, found.start() - 60):found.end() + 60].strip()
        fail(
            '%s calls `%s` the pin, but layout/harness/env.py declares `%s`: '
            '"...%s..."' % (label, found.group(1), pin, quoted)
        )

if not stated_in_required_doc:
    fail(
        "%s never states this repository's KLayout pin (`%s`). Its section 6 "
        "scores a DRC/LVS verdict table, and a verdict is only evidence about "
        "the engine that produced it -- an outside reader must not have to "
        "open layout/harness/env.py to learn which one that was." % (pin_stated_doc, pin)
    )

if not failed:
    print(
        "%d documents state or restate the KLayout pin consistently with "
        "layout/harness/env.py (%s)" % (len(doc_args), pin)
    )
sys.exit(1 if failed else 0)
PY
}

# --- The layer census rule (see the header) --------------------------------
#
# Grades every `layer_indexes()` census a `layout/evidence/*/PROOF-*.md` prints
# against the GDS that document names, as a set. This is the one guard here
# that opens a binary artifact: `klayout.db` (the `klayout` pip wheel's Python
# module, NOT the standalone KLayout application binary the DRC/LVS decks run
# on) is imported lazily, only once a census claim has actually been found, so
# a tree that makes no such claim needs nothing new -- and a tree that makes
# one and cannot import it FAILS rather than skipping, exactly as a missing
# python3 does above.
#
# Narrow by construction, three ways:
#
#   * only brace-lists whose members are all `<layer>/<datatype>` pairs are
#     candidates, and only where `layer_indexes()` is mentioned in a window
#     around the match. A brace-list on its own is not a census claim -- this
#     is the same discipline the PIN RESTATEMENT RULE applies to version
#     numbers, which are likewise only graded in the shapes that assert;
#   * the GDS is resolved, never assumed: an explicitly named sibling in the
#     same evidence directory wins, otherwise the block's own GDS from BLOCKS.
#     `vco-layout` alone commits six GDS files, so "the block's GDS" is a real
#     choice and not a tautology. A census whose file resolves to nothing fails
#     asking to be named, rather than passing unchecked;
#   * an occurrence inside `~~...~~` is skipped, because this repository
#     corrects evidence by striking the wrong value in place and stating the
#     right one beside it. #660's fix to `vco-layout/PROOF-erc.md` left exactly
#     that shape behind -- a struck 14-member list, a live 15-member one, in
#     one sentence -- and a rule that graded the strike would fail every
#     correctly-corrected document.
layer_census_rule() {
  local evidence="$1" blocks="$2"
  python3 - "${evidence}" "${blocks}" <<'PY'
import glob
import os
import re
import sys

evidence, blocks_spec = sys.argv[1], sys.argv[2]

failed = False


def fail(msg):
    global failed
    failed = True
    sys.stderr.write("FAIL: %s\n" % msg)


# Each block's own GDS, keyed by evidence directory -- taken from BLOCKS in the
# caller rather than restated here, so the two lists cannot disagree.
default_gds = {}
for item in blocks_spec.split(";"):
    if not item:
        continue
    directory, gds = item.split("|")
    default_gds[directory] = gds

# A census: `{21/0, 22/0, ...}`, every member a layer/datatype pair. Integer
# pairs only, so a set-builder or an inline JSON object cannot match.
CENSUS_RE = re.compile(
    r"\{\s*[0-9]+\s*/\s*[0-9]+(?:\s*,\s*[0-9]+\s*/\s*[0-9]+)*\s*\}"
)
MEMBER_RE = re.compile(r"([0-9]+)\s*/\s*([0-9]+)")
# Struck text, on the whitespace-collapsed document (so a strike may wrap
# freely in the source). Non-greedy, so consecutive strikes pair as written.
STRUCK_RE = re.compile(r"~~.+?~~")
GDS_RE = re.compile(r"\b([A-Za-z0-9_]+\.gds)\b")

# What makes a brace-list a census *claim* rather than a brace-list: the
# document saying which tool call produced it. Every real one in this tree
# names `layer_indexes()` within a sentence or two.
MENTION = "layer_indexes"

# How far from the match the mention may sit. The `before` reach is the wider
# of the two because #660's correction shape puts a whole struck census between
# the mention and the live list it introduces:
#   "...the file's own `layer_indexes()`: ~~`{...14 members...}`~~ -> **`{...}`**"
REACH_BEFORE = 250
REACH_AFTER = 120

# How far back an explicitly named sibling GDS may sit and still be the subject
# of the census. Same value as REACH_BEFORE on purpose: the two questions
# ("is this a census?" / "of what?") are answered from the same sentence.
GDS_REACH = 250

_census_cache = {}
_import_error = None


def actual_census(path):
    """The layer/datatype set the committed GDS at ``path`` really contains.

    Imports ``klayout.db`` on first use only. Returns None if it cannot be
    imported, having reported that once -- this rule's whole contract is that
    the dependency is demanded where a claim exists and nowhere else.
    """
    global _import_error
    if path in _census_cache:
        return _census_cache[path]
    try:
        import klayout.db as db  # noqa: PLC0415 - deliberately lazy
    except ImportError as exc:
        if _import_error is None:
            _import_error = str(exc)
            fail(
                "a PROOF document states a `layer_indexes()` census, but "
                "`klayout.db` cannot be imported (%s), so the census cannot be "
                "graded against the GDS it describes. Install the `klayout` pip "
                "wheel -- `pip install klayout`, which "
                ".github/workflows/ci.yml already does earlier in this job for "
                "layout/tests/. A partial pass is not a pass: issue #660's "
                "14-vs-15-member census survived five weeks precisely because "
                "nothing opened the file." % _import_error
            )
        return None
    layout = db.Layout()
    layout.read(path)
    got = frozenset(
        (layout.get_info(i).layer, layout.get_info(i).datatype)
        for i in layout.layer_indexes()
    )
    _census_cache[path] = got
    return got


def render(members):
    return "{%s}" % ", ".join(
        "%d/%d" % pair for pair in sorted(members)
    )


n_docs = n_graded = n_struck = 0

for proof in sorted(glob.glob(os.path.join(evidence, "*", "PROOF-*.md"))):
    directory = os.path.basename(os.path.dirname(proof))
    rel = "layout/evidence/%s/%s" % (directory, os.path.basename(proof))
    try:
        with open(proof, encoding="utf-8") as fh:
            flat = re.sub(r"\s+", " ", fh.read())
    except OSError as exc:  # pragma: no cover - unreadable committed file
        fail("cannot read %s: %s" % (rel, exc))
        continue

    struck = [(m.start(), m.end()) for m in STRUCK_RE.finditer(flat)]
    graded_here = 0

    for m in CENSUS_RE.finditer(flat):
        window = flat[max(0, m.start() - REACH_BEFORE):m.end() + REACH_AFTER]
        if MENTION not in window:
            continue

        if any(start <= m.start() < end for start, end in struck):
            # Struck history, quotable on purpose -- see this rule's header.
            n_struck += 1
            continue

        quoted = flat[max(0, m.start() - 90):m.end() + 40].strip()

        # --- Which GDS does this census name? ---------------------------------
        gds = None
        named = [
            found.group(1)
            for found in GDS_RE.finditer(flat[max(0, m.start() - GDS_REACH):m.start()])
        ]
        for candidate in reversed(named):
            if os.path.isfile(os.path.join(evidence, directory, candidate)):
                gds = candidate
                break
        if gds is None:
            gds = default_gds.get(directory)
        if gds is None:
            siblings = sorted(
                os.path.basename(p)
                for p in glob.glob(os.path.join(evidence, directory, "*.gds"))
            )
            if len(siblings) == 1:
                gds = siblings[0]

        if gds is None:
            fail(
                '%s states a `layer_indexes()` census that resolves to no '
                'committed GDS: "...%s...". This directory is not one of the '
                "four PLL blocks and does not hold exactly one .gds, so name "
                "the file in the sentence (e.g. `vco_bandsel_mirror.gds`) -- a "
                "census whose subject a reader cannot identify is not a "
                "checkable claim." % (rel, quoted)
            )
            continue

        path = os.path.join(evidence, directory, gds)
        if not os.path.isfile(path):
            fail(
                "%s states a `layer_indexes()` census of `%s`, which is not "
                "committed beside it." % (rel, gds)
            )
            continue

        actual = actual_census(path)
        if actual is None:
            continue

        claimed = frozenset(
            (int(layer), int(datatype))
            for layer, datatype in MEMBER_RE.findall(m.group(0))
        )
        n_graded += 1
        graded_here += 1

        if claimed != actual:
            missing = actual - claimed
            extra = claimed - actual
            detail = []
            if missing:
                detail.append("omits %s" % render(missing))
            if extra:
                detail.append("names %s, absent from the file" % render(extra))
            fail(
                "%s states a %d-member `layer_indexes()` census of `%s`, but "
                "that committed GDS has %d layers: the claim %s. Actual census: "
                '%s. Quoted: "...%s...". Re-derive it rather than adjusting the '
                "count -- issue #660's own defect was a hand-transcribed list "
                "that dropped `0/0`, and the fix is the one-liner each "
                "PROOF-erc.md quotes: python3 -c \"import klayout.db as db; "
                "ly = db.Layout(); ly.read('%s'); print(sorted('%%d/%%d' %% "
                "(ly.get_info(i).layer, ly.get_info(i).datatype) for i in "
                'ly.layer_indexes()))"'
                % (
                    rel,
                    len(claimed),
                    gds,
                    len(actual),
                    " and ".join(detail),
                    render(actual),
                    quoted,
                    os.path.relpath(path, os.path.dirname(os.path.dirname(evidence))),
                )
            )

    if graded_here:
        n_docs += 1

print("layout/evidence/ PROOF-*.md layer_indexes() censuses say:")
if n_graded:
    print(
        "  %d census claim(s) across %d document(s) match the committed GDS "
        "each one names (%d struck occurrence(s) skipped as history)"
        % (n_graded, n_docs, n_struck)
    )
else:
    print(
        "  no document states a layer_indexes() census (%d struck occurrence(s) "
        "skipped as history); klayout.db was not needed" % n_struck
    )
sys.exit(1 if failed else 0)
PY
}

BLOCK_PIN_SPEC=""
for entry in "${pin_entries[@]}"; do
  BLOCK_PIN_SPEC="${BLOCK_PIN_SPEC}${BLOCK_PIN_SPEC:+;}${entry}"
done

# `<evidence dir>|<block GDS basename>` for the layer census rule's default
# resolution, from BLOCKS above so the two lists cannot disagree.
BLOCK_GDS_SPEC=""
for entry in "${BLOCKS[@]}"; do
  IFS='|' read -r _label dir gds _top <<<"${entry}"
  BLOCK_GDS_SPEC="${BLOCK_GDS_SPEC}${BLOCK_GDS_SPEC:+;}${dir}|${gds}"
done

if [ "${have_python}" = yes ]; then
  klayout_pin_rule "${EVIDENCE}" "${HARNESS_ENV}" "${BLOCK_PIN_SPEC}" || status=1
  echo

  pin_doc_args=()
  for doc in "${PIN_DOCS[@]}"; do
    pin_doc_args+=("${doc}=${REPO_ROOT}/${doc}")
  done
  pin_restatement_rule "${HARNESS_ENV}" "${PIN_STATED_DOC}" "${pin_doc_args[@]}" || status=1
  echo

  layer_census_rule "${EVIDENCE}" "${BLOCK_GDS_SPEC}" || status=1
  echo
else
  fail "python3 is not on PATH -- the KLayout pin rule and the layer census rule could not run, and a partial pass is not a pass"
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

# The DEFERRAL half of the same rule (see the header). A bare deferral --
# "(once drawn)", "layout ... when drawn", "if ever laid out" -- asserts the
# same falsehood as a negation without using a negation word, so ABSENCE
# above cannot see it. The regex deliberately requires the participle to
# follow the deferral marker with no noun phrase in between: a deferral that
# NAMES its subject ("when the loop filter is drawn", "once the top level is
# drawn") is checkable prose about something genuinely undrawn and must stay
# legal, while a bare one necessarily defers whatever the sentence is about
# -- which, in the sentence this rule was written for, was the whole flow.
#
# Unlike ABSENCE, the participle carries no layout noun of its own ("drawn"
# is the whole claim), so the deferral must additionally sit near one:
# DEFERRAL_CONTEXT below must appear within ~60 characters. That is what
# keeps this off the sim campaigns' own vocabulary -- a Monte-Carlo sample
# "scored once drawn from the grid" is not a statement about layout.
DEFERRAL = re.compile(
    r"(?<![a-z-])(?:once|when|until|after|if)\s+"
    r"(?:it\s+is\s+|they\s+are\s+|these\s+are\s+|ever\s+)?"
    r"(?:drawn|laid\s+out)(?![a-z-])"
)
DEFERRAL_CONTEXT = re.compile(r"layout|gds|\bdrc\b|\blvs\b|extract|floorplan")

failed = False
for pattern, context, complaint, remedy in (
    (
        ABSENCE,
        None,
        "asserts layout does not exist without saying at what scope",
        "so an unqualified absence claim is false. Name the scope -- the "
        "assembled top level, the extracted post-layout netlist -- within "
        "~100 characters of the negation, or drop the sentence.",
    ),
    (
        DEFERRAL,
        DEFERRAL_CONTEXT,
        "defers layout to the future without saying what is deferred",
        "so a bare \"once drawn\" reads as though none of it is drawn yet. "
        "Name what the deferral is about -- the assembled top level, the "
        "loop filter -- between the deferral word and the participle, or "
        "name the scope within ~100 characters of it.",
    ),
):
    for m in pattern.finditer(low):
        start, end = max(0, m.start() - 100), m.end() + 100
        if any(tok in low[start:end] for tok in scope_tokens):
            continue
        if context is not None and not context.search(
            low[max(0, m.start() - 60):m.end() + 60]
        ):
            continue
        failed = True
        sys.stderr.write(
            "FAIL: %s %s: \"...%s...\"\n"
            "      PLL sub-block layouts are committed under "
            "layout/evidence/, %s Accepted scope words: %s\n"
            % (
                label,
                complaint,
                flat[start:end].strip(),
                remedy,
                ", ".join(scope_tokens) or "(none)",
            )
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
    "and spec/pll.md (ratified: ${spec_ratified}); no unscoped absence-of-layout claim" \
    "and no bare deferral of layout to the future;" \
    "every stated block footprint matches layout/evidence/area-audit/area-audit.md," \
    "including spec/pll.md's own '## Area' section;" \
    "every committed klt erc report's provenance matches the GDS and spec beside it," \
    "on the klt version .github/workflows/ci.yml pins;" \
    "and every document that states this repository's KLayout pin states the one" \
    "layout/harness/env.py declares;" \
    "and every layer_indexes() census a PROOF-*.md states matches, as a set," \
    "the committed GDS it names"
fi

exit "${status}"
