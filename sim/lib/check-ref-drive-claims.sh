#!/usr/bin/env bash
#
# Fails if a document that quotes a shell command as its own evidence quotes one
# whose file glob cannot reach the files that would falsify it, or if the
# REF-drive uniformity claim that command backs is not true of the decks the
# command actually finds.
#
# WHY THIS EXISTS (issue #237)
#
# docs/chipalooza/challenge-5-proposal.md's Reference input row, and
# spec/decision-records/DR-019's Context section, both rest on the same
# sentence: every testbench in this repository that drives `REF` drives it
# identically, so the levels, edge-rate and duty lines of the ratified
# Reference input contract are conditions nothing has ever varied. Both
# documents hand the reader a command to check it with:
#
#     grep -n '^vref ' sim/*/testbench/*.sp
#
# On 2026-09-25 that command returned ten decks, all one shape, and the claim
# read as confirmed. The repository held thirteen REF-driving decks, and the
# three the command could not see included
# `sim/reference-input-contract/testbench/tb_reference_input_contract.spice` --
# the one deck in this repository that varies the reference waveform, landed by
# the *same commit* (#518, issue #499) that wrote both sentences. Its deck is
# `.spice`; the glob says `*.sp`. So the quoted command did not merely fail to
# confirm the claim, it silently excluded the counterexample and returned a
# clean answer -- to a reader of the one document in this repository written to
# be emailed verbatim to someone who cannot re-run anything else.
#
# No existing check could see it. check-record-supersession.sh grades cited
# *records*; check-pvt-coverage-claims.sh grades the corners a row was measured
# at; check-spec-row-coverage.sh grades spec rows and decision records;
# check-io-list-coverage.sh grades ports; check-issue-reference-state.sh grades
# the forge. All of them grade a document against evidence the document names.
# This one grades the *reachability of the evidence a quoted command promises*:
# a reproduction command offered as proof has to be able to return the thing
# that would disprove it.
#
# THE RULES
#
# 1. DECK ENUMERATION. Scan every committed SPICE deck under `sim/*/testbench*/`
#    for an independent voltage source driving the `ref` node, and classify each
#    one's `pulse(...)` shape (below). Fail if the scan finds none: a parser
#    that enumerates nothing must not look like a clean tree.
#
# 2. GLOB COMPLETENESS. For every `grep` command a graded document quotes whose
#    pattern matches at least one of those REF source lines -- i.e. every
#    command the document offers as the enumeration of how REF is driven -- the
#    glob it uses must not be narrowed by its own filename extension. The check
#    re-expands each glob with its trailing `*.<ext>` replaced by `*`, keeps the
#    files whose content the command's own pattern matches, and fails on any
#    that the quoted glob cannot reach.
#
#    Only the EXTENSION is relaxed, not the directory part. A glob that names
#    `sim/*/testbench/` cannot be judged against decks under some other
#    directory without guessing what the author meant to enumerate; the
#    extension is different, because `*.sp` versus `*.spice` is not a scope
#    decision anyone makes on purpose. (This repository writes both:
#    sim/harness/batch.py already loops `for f in *.spice *.sp`.)
#
# 3. DEVIATION IS NAMED. A document asserting REF-drive uniformity must name --
#    by path or by campaign directory -- every deck whose shape deviates. One
#    exists today and both documents do name it, so this rule is the one that
#    fires the day a second one lands quietly.
#
# 4. AN UNQUALIFIED CLAIM IS TRUE OF WHAT THE COMMAND CAN REACH. A uniformity
#    claim that does not scope itself -- whose own wording says nothing about
#    records, measurement or evidence -- must hold across every deck its
#    command can reach: the union of what the quoted glob returns and what
#    rule 2's widening adds. The union, not the glob's own output, is
#    deliberate: grading the sentence only against the files the glob happens
#    to reach would make narrowing the glob a way to make the sentence true
#    again, which is the failure this whole check exists for.
#
#    A claim that IS scoped ("every testbench that has produced a record …")
#    is exempt from this rule and held to rule 5 instead, which is the rule
#    that makes the scoping honest. Keying on a word rather than on meaning is
#    a real limit: an author can satisfy rule 4 by writing "record" into a
#    sentence that does not mean it. Rule 5 is what that author still cannot
#    get past, and it needs no wording at all.
#
# 5. A DEVIATING DECK HAS PRODUCED NO EVIDENCE -- UNLESS THE PREMISE WAS
#    RE-ARGUED, IN A NAMED DECISION RECORD. Every deck classified as a
#    deviation must belong to a campaign with no committed record. This is the
#    substance the wording is about: `spec/pll.md`'s Reference input row
#    excludes reference-source quality from the jitter and spur budgets, and
#    every number in those rows is the block's own contribution *against an
#    ideal reference*. The day a deck that varies the reference waveform
#    produces a record, that premise stops being true by construction and has
#    to be re-argued -- so it must not pass quietly, whatever any document
#    happens to say. Unlike rules 2-4, this one grades the tree alone.
#
#    That day arrived with issue #509, and the rule's own closing sentence said
#    what the price of passing is: "Re-state the Reference input row and the
#    exclusion it carries before this check is made to pass." So the rule now
#    has exactly one way through, and it is not a flag: the campaign must be
#    named in `REARGUED` below, mapping it to the decision record that
#    re-argues the premise, and this check verifies that record exists, is not
#    a stub, and names the campaign back. Editing a table in a CI script and
#    landing a ratified decision record is a deliberate act with a reviewer in
#    front of it; an environment variable or a file dropped in a directory is
#    not, which is why neither is offered.
#
#    A re-argued campaign is still counted and still reported as a deviation --
#    the summary line names it. What the allowance buys is "this deviation is
#    accounted for", never "this deviation is invisible".
#
# WHAT "SHAPE" MEANS
#
# ngspice `pulse(v1 v2 td tr tf pw per)`. A deck is classified IDEAL when it
# starts at a literal `0` (v1) and uses `200p` for both edges (tr, tf) -- the
# full-rail, fast-edge, construction-ideal reference every record in this
# repository was measured against. Everything else is a DEVIATION. The rails
# (v2) and timings (td, pw, per) are deliberately not compared: campaigns
# legitimately name their rail differently (`vsup`, `vdd_val`, `v_lo`) and two
# decks trim `pw` by a single edge time. What the contract's three unmeasured
# lines -- levels, edge rate, duty -- actually live in is v1/v2 versus the rail,
# tr/tf, and pw versus per, and a deck that varies any of them shows it in v1,
# tr or tf unless it varies duty alone. That residual is a real limit of this
# classifier and is stated here rather than implied away.
#
# A REFERENCE THAT IS NOT A `pulse()` AT ALL
#
# The enumeration above reads one shape of line: an independent source driving
# the `ref` node with a `pulse(...)`. `sim/reference-phase-transfer` (#509)
# drives `ref` from a **behavioural** source instead -- two `pulse()` trains on
# private nodes, blended onto `ref` by a `b`-source so the reference edge can be
# displaced *in time* mid-run -- and the original regex could not see it: its
# `v<name> ref 0 pulse(` shape matches neither `vrefa refa 0 pulse(`, which
# drives a private node, nor `bref ref 0 v='...'`, which is not a `pulse()`.
#
# That blindness is the #237 defect wearing different clothes. A check that
# enumerates "how REF is driven" and cannot see the one deck in the repository
# whose whole purpose is to drive it differently reports a clean tree for the
# same reason the original `*.sp` glob did: the counterexample was outside the
# pattern, not absent from the tree. So the scan now also matches a dependent
# or behavioural source on `ref` (`b`/`e`/`g`, and a `pwl`/`pulse`-less `v`),
# and classifies every one of them a DEVIATION *without* inspecting arguments:
# a synthesised reference is not the construction-ideal periodic pulse whatever
# its expression says, and pretending to parse an arbitrary B-source expression
# would be a classifier that fails silently rather than one that abstains.
#
# WHAT IT DOES NOT DO
#
# It does not run ngspice, open a record, or check that a deck measures what it
# says -- rule 5 asks only whether a campaign's `records/` directory holds one.
# It reads committed decks and committed Markdown. It cannot grade a document
# that makes the uniformity claim and quotes no command for it (rules 3 and 5
# still apply; rules 2 and 4 have nothing to attach to), and it deliberately
# does not grade netlist snapshots under `sim/*/netlist-snapshots/` -- those are
# generated artifacts of a run, not decks anyone maintains.
#
# Usage: sim/lib/check-ref-drive-claims.sh
# Exit codes: 0 every quoted REF-enumerating command reaches every REF-driving
#             deck, every uniformity claim holds or scopes itself, and every
#             deviating deck either has produced no evidence or is re-argued in
#             a named decision record;
#             1 a quoted glob excludes a matching deck, a deviating deck is
#             unnamed, an unqualified uniformity claim is false over the decks
#             its own command can reach, a deviating deck has a committed
#             record with no re-argument, a named re-argument is missing or does
#             not name its campaign, a graded document is missing, or the deck
#             scan found nothing.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# The documents that make, or could make, the REF-drive claim. The proposal is
# the outward-facing one; DR-019 is where the claim originates and the record
# the proposal cites for it. README.md and sim/CHARACTERIZATION.md are graded
# too so the claim cannot be restated there ungraded.
GRADED=(
  "README.md"
  "sim/CHARACTERIZATION.md"
  "docs/chipalooza/challenge-5-proposal.md"
  "spec/decision-records/DR-019-reference-input-contract-owner-and-source-quality-exclusion.md"
)

if ! command -v python3 >/dev/null 2>&1; then
  echo "FAIL: python3 is not on PATH -- this check could not run, and a" \
    "check that did not run is not a check that passed" >&2
  exit 1
fi

python3 - "${REPO_ROOT}" "${GRADED[@]}" <<'PY'
import glob
import os
import re
import sys

repo_root, graded = sys.argv[1], sys.argv[2:]

# An independent source driving the `ref` node: `vref ref 0 pulse(...)`, and
# the same line under any other instance name a deck might use.
REF_SOURCE = re.compile(
    r"^(?P<inst>v[a-z0-9_]*)[ \t]+ref[ \t]+0[ \t]+pulse\((?P<args>[^)]*)\)",
    re.IGNORECASE | re.MULTILINE,
)

# A SYNTHESISED reference: anything else that drives the `ref` node from a
# source instance -- a behavioural `b`-source, a controlled `e`/`g` source, or a
# `v` source whose waveform is not a `pulse()` (a `pwl`, a table, an
# expression). `sim/reference-phase-transfer` (#509) is the first: it blends two
# private `pulse()` trains onto `ref` through a `b`-source so the reference edge
# can be displaced in time mid-run. Every match is a DEVIATION with no argument
# parsing -- see "A REFERENCE THAT IS NOT A `pulse()` AT ALL" in the header for
# why abstaining from parsing is the honest classification here.
REF_SYNTHESISED = re.compile(
    r"^(?P<inst>[bevg][a-z0-9_]*)[ \t]+ref[ \t]+0[ \t]+(?P<rest>(?!pulse\()\S.*)$",
    re.IGNORECASE | re.MULTILINE,
)

# The decks anyone maintains: `sim/<campaign>/testbench*/`. Netlist snapshots
# are generated copies of these and are deliberately out of scope.
DECK_GLOBS = ("sim/*/testbench*/*.sp", "sim/*/testbench*/*.spice")

# An inline-code span, which is how both graded documents quote their command.
INLINE_CODE = re.compile(r"`([^`\n]+)`")

# The uniformity claim, in either document's phrasing. Kept deliberately loose
# on what sits between "testbench" and the verb, because both documents put a
# qualifier there ("in this repository that drives `REF`", "here that drives
# `REF`") and a future one will put a different qualifier there.
UNIFORMITY = re.compile(
    r"every\s+testbench[^.]{0,160}?drives?\s+(?:it|`?REF`?)\s+"
    r"(?:the\s+same\s+way|identically)",
    re.IGNORECASE,
)

# What makes a uniformity claim scoped rather than absolute: the claim's own
# wording restricts it to the decks that produced evidence. See rule 4 in the
# header for why this keys on a word, and what rule 5 does about that.
SCOPING = re.compile(r"\b(records?|measured|measurement|evidence)\b", re.IGNORECASE)


def shape_of(args):
    """Classify a `pulse(v1 v2 td tr tf pw per)` argument list.

    Returns ("ideal", None) or ("deviation", <why>). See the script header for
    why only v1, tr and tf are compared.
    """
    fields = args.replace(",", " ").split()
    if len(fields) < 5:
        return "deviation", "pulse() has %d arguments, expected 7" % len(fields)
    v1, _v2, _td, tr, tf = fields[:5]
    why = []
    if v1 != "0":
        why.append("starts at %s rather than a literal 0" % v1)
    if tr != "200p" or tf != "200p":
        why.append("edges are %s/%s rather than 200p/200p" % (tr, tf))
    if why:
        return "deviation", "; ".join(why)
    return "ideal", None


# ---------------------------------------------------------------- rule 1
decks = {}  # repo-relative path -> (line number, source line, shape, why)
for pattern in DECK_GLOBS:
    for path in sorted(glob.glob(os.path.join(repo_root, pattern))):
        rel = os.path.relpath(path, repo_root)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        m = REF_SOURCE.search(text)
        if m:
            line_no = text.count("\n", 0, m.start()) + 1
            shape, why = shape_of(m.group("args"))
            decks[rel] = (line_no, m.group(0), shape, why)
            continue
        m = REF_SYNTHESISED.search(text)
        if not m:
            continue
        line_no = text.count("\n", 0, m.start()) + 1
        decks[rel] = (
            line_no,
            m.group(0),
            "deviation",
            "`ref` is synthesised by source %s, not driven by an independent "
            "pulse() -- the reference waveform is constructed by the deck"
            % m.group("inst"),
        )

if not decks:
    sys.stderr.write(
        "FAIL: found no REF-driving deck under %s -- enumeration is broken, and "
        "a parser that reads nothing must not look like a clean tree\n"
        % " / ".join(DECK_GLOBS)
    )
    sys.exit(1)

deviations = {p: v for p, v in decks.items() if v[2] == "deviation"}


def campaign_of(rel_path):
    parts = rel_path.split(os.sep)
    return parts[1] if len(parts) > 1 else rel_path


def records_of(campaign):
    rec_dir = os.path.join(repo_root, "sim", campaign, "records")
    if not os.path.isdir(rec_dir):
        return []
    return sorted(n for n in os.listdir(rec_dir) if n.endswith(".md"))


failed = False
commands_checked = 0
claims_checked = 0

# ---------------------------------------------------------------- rule 5
#
# The only way past rule 5: campaign -> the decision record that re-argues the
# "every number is measured against an ideal reference" premise for it. Adding
# an entry is a deliberate code change with a reviewer in front of it, and the
# record it names is verified to exist, to be more than a stub, and to name the
# campaign back -- so an entry cannot be a bare assertion that the work was
# done. See rule 5 in the header.
REARGUED = {
    # #509: this campaign perturbs the reference edge IN TIME on purpose, to
    # measure the 20*log10(N) transfer the exclusion asserts. It reports no
    # jitter and no spur number, which is what keeps the premise true for the
    # rows that do -- DR-027 states that in as many words.
    "reference-phase-transfer": (
        "spec/decision-records/"
        "DR-027-reference-phase-transfer-measures-the-exclusions-transfer.md"
    ),
    # #527/#552: this campaign phase-steps REF to trigger the LOCK-pad
    # deassert transition and reads the trim-code window it selects. DR-029
    # is a negative-result method characterization -- it reports deassert
    # latency and trim-code viability, no jitter or spur number, so the
    # ideal-reference premise the rest of this tree's jitter/spur/phase-
    # transfer figures rest on is untouched.
    "lock-window-bisection": (
        "spec/decision-records/"
        "DR-029-ref-phase-step-bisection-measures-the-wrong-quantity.md"
    ),
}

#: A decision record short enough to be a placeholder is not a re-argument.
#: 1500 bytes is roughly the template's own skeleton with nothing said in it.
REARGUMENT_MIN_BYTES = 1500

reargued_with_records = []

for path, (_line, _src, _shape, why) in sorted(deviations.items()):
    campaign = campaign_of(path)
    found = records_of(campaign)
    if not found:
        continue

    dr_rel = REARGUED.get(campaign)
    if dr_rel is None:
        failed = True
        sys.stderr.write(
            "FAIL: `%s` varies the reference waveform (%s) and its campaign "
            "sim/%s/ has %d committed record(s), the first being %s. Every "
            "jitter, spur and phase number this repository reports is stated "
            "against an ideal reference *by construction*; a record measured "
            "with a varied reference means that premise now has to be argued "
            "rather than assumed. Re-state the Reference input row and the "
            "exclusion it carries in a decision record, then name that record "
            "against `%s` in this check's own REARGUED table -- do not make "
            "this check pass any other way.\n"
            % (path, why, campaign, len(found), found[0], campaign)
        )
        continue

    dr_path = os.path.join(repo_root, dr_rel)
    if not os.path.isfile(dr_path):
        failed = True
        sys.stderr.write(
            "FAIL: sim/%s/ is listed in this check's REARGUED table against "
            "%s, and that file does not exist. A re-argument this check cannot "
            "read is not a re-argument.\n" % (campaign, dr_rel)
        )
        continue

    with open(dr_path, encoding="utf-8") as fh:
        dr_text = fh.read()
    if len(dr_text) < REARGUMENT_MIN_BYTES:
        failed = True
        sys.stderr.write(
            "FAIL: %s is only %d bytes, below the %d-byte floor for a "
            "re-argument of the ideal-reference premise. A stub is not an "
            "argument.\n" % (dr_rel, len(dr_text), REARGUMENT_MIN_BYTES)
        )
        continue
    if campaign not in dr_text:
        failed = True
        sys.stderr.write(
            "FAIL: %s is named as the re-argument for sim/%s/ and never "
            "mentions `%s`. The record has to be about the campaign it "
            "excuses.\n" % (dr_rel, campaign, campaign)
        )
        continue

    reargued_with_records.append((campaign, dr_rel, len(found)))


def parse_grep(command):
    """Split a quoted `grep` command into (pattern, [globs]), or None."""
    tokens = command.split()
    if not tokens or tokens[0] != "grep":
        return None
    rest = [t for t in tokens[1:] if not t.startswith("-")]
    if len(rest) < 2:
        return None
    pattern = rest[0].strip("'\"")
    globs = [t for t in rest[1:] if "/" in t or "*" in t]
    if not globs:
        return None
    return pattern, globs


def relax_extension(pattern):
    """`a/b/*.sp` -> `a/b/*`. Only the extension is relaxed (see the header)."""
    head, tail = os.path.split(pattern)
    if tail.startswith("*.") or "." in tail:
        return os.path.join(head, "*")
    return pattern


for doc in graded:
    doc_path = os.path.join(repo_root, doc)
    if not os.path.isfile(doc_path):
        sys.stderr.write("FAIL: %s does not exist\n" % doc)
        failed = True
        continue
    with open(doc_path, encoding="utf-8") as fh:
        text = fh.read()

    claim_spans = [m.group(0) for m in UNIFORMITY.finditer(text)]
    claims_uniformity = bool(claim_spans)
    unqualified = [c for c in claim_spans if not SCOPING.search(c)]
    claims_checked += len(claim_spans)

    for command in INLINE_CODE.findall(text):
        parsed = parse_grep(command)
        if parsed is None:
            continue
        pattern, globs = parsed
        try:
            matcher = re.compile(pattern, re.MULTILINE)
        except re.error:
            continue

        # Is this command about how REF is driven? It is if its own pattern
        # matches a REF source line this check found. Anything else is some
        # other grep the document happens to quote, and none of this applies.
        if not any(matcher.search(v[1]) for v in decks.values()):
            continue
        commands_checked += 1

        quoted = set()
        widened = set()
        for g in globs:
            for path in glob.glob(os.path.join(repo_root, g)):
                quoted.add(os.path.relpath(path, repo_root))
            for path in glob.glob(os.path.join(repo_root, relax_extension(g))):
                rel = os.path.relpath(path, repo_root)
                if not os.path.isfile(path):
                    continue
                try:
                    with open(path, encoding="utf-8") as fh:
                        body = fh.read()
                except (UnicodeDecodeError, OSError):
                    continue
                if matcher.search(body):
                    widened.add(rel)

        # -------------------------------------------------------- rule 2
        missed = sorted(widened - quoted)
        if missed:
            failed = True
            sys.stderr.write(
                "FAIL: %s quotes `%s` as the enumeration behind its REF-drive "
                "claim, but that glob's extension excludes %d file(s) its own "
                "pattern matches:\n%s\n"
                "A reproduction command offered as proof has to be able to "
                "return the thing that would disprove it. Widen the glob "
                "(this repository writes both `.sp` and `.spice`; see "
                "sim/harness/batch.py) rather than narrowing the claim to the "
                "files that happen to agree with it.\n"
                % (
                    doc,
                    command,
                    len(missed),
                    "".join(
                        "    %s%s\n"
                        % (
                            p,
                            "  <-- DEVIATES: %s" % decks[p][3]
                            if p in deviations
                            else "",
                        )
                        for p in missed
                    ),
                )
            )

        # -------------------------------------------------------- rule 4
        if not unqualified:
            continue
        reachable = sorted(quoted | widened)
        shapes = {decks[p][2] for p in reachable if p in decks}
        if len(shapes) > 1:
            failed = True
            sys.stderr.write(
                "FAIL: %s asserts, without scoping it, that %s, but `%s` "
                "reaches decks of more than one shape:\n%s\n"
                "State the exception rather than the uniformity -- the claim "
                "that survives is about what has been *measured*, not about "
                "what decks exist.\n"
                % (
                    doc,
                    '"%s"' % " ".join(unqualified[0].split()),
                    command,
                    "".join(
                        "    %-64s %s%s\n"
                        % (
                            p,
                            decks[p][2].upper(),
                            " (%s)" % decks[p][3] if decks[p][3] else "",
                        )
                        for p in reachable
                        if p in decks
                    ),
                )
            )

    # ------------------------------------------------------------ rule 3
    if claims_uniformity:
        for path in sorted(deviations):
            campaign = path.split(os.sep)[1] if os.sep in path else path
            if path in text or ("sim/%s" % campaign) in text:
                continue
            failed = True
            sys.stderr.write(
                "FAIL: %s asserts every testbench drives REF the same way and "
                "never names `%s`, which does not (%s). A claim of uniformity "
                "has to name its exceptions.\n"
                % (doc, path, deviations[path][3])
            )

if failed:
    sys.exit(1)

if reargued_with_records:
    carrying = "; ".join(
        "sim/%s (%d record(s), re-argued in %s)" % (c, n, dr)
        for c, dr, n in sorted(reargued_with_records)
    )
else:
    carrying = "none of the deviating ones carrying a record"

print(
    "OK: %d REF-driving decks under %s (%d ideal, %d deviating, %s); %d quoted "
    "REF-enumerating command(s) across %d uniformity claim(s) reach every deck "
    "their own pattern matches, and every claim names its exceptions"
    % (
        len(decks),
        " / ".join(DECK_GLOBS),
        len(decks) - len(deviations),
        len(deviations),
        carrying,
        commands_checked,
        claims_checked,
    )
)
PY
