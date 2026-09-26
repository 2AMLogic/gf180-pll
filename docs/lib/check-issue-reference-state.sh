#!/usr/bin/env bash
#
# Fails if an outward-facing document names an issue this repository does not
# have, states an issue's open/closed state that the forge contradicts, or
# hands an open gap to an owner that is closed.
#
# WHY THIS EXISTS (issue #237)
#
# Six checks already grade docs/chipalooza/challenge-5-proposal.md, and every
# one of them grades it against something committed in this tree:
#
#   sim/lib/check-readme-status.sh              counts vs. the sim/ tree
#   sim/lib/check-characterization-coverage.sh  the report's rows and its count
#   sim/lib/check-record-supersession.sh        cited records vs. the graph
#   layout/lib/check-layout-status-claims.sh    layout claims vs. layout/
#   spec/lib/check-spec-row-coverage.sh         section 5 vs. spec/pll.md
#   design/lib/check-io-list-coverage.sh        the I/O list vs. the netlist
#
# A tree is a thing a check can read. The other half of what this document
# asserts is not in the tree at all: it tells its reader, repeatedly, that a
# gap it cannot close is *owned* -- "Tracked at issue #13", "routed to their
# owning issues (#9, #10, #11)", "issue #499 (open)". Those are claims about
# the forge, and the forge moves without touching this repository. Nothing
# could see them go stale, and they did:
#
#   - #13 closed 2026-09-08 (completed). Seventeen days later section 5's
#     random/noise-driven period-jitter row -- "the one row this proposal
#     cannot report a number for at any maturity" -- still read "Tracked at
#     issue #13", and its Source column still read "issue #13 (open)", a
#     state annotation that was by then simply false.
#   - #17 closed 2026-09-08 (completed), and it is the *floorplan* issue.
#     Sections 6 and 7 named it as the tracker for **top-level assembly**,
#     work that is owned by #297 and has never been mentioned in this
#     document.
#   - #9, #10 and #11 all closed. Section 7 item 4 told the reader that
#     supply-sensitivity's three FAILing criteria "are already routed to
#     their owning issues (#9, #10, #11)".
#   - `Epic #542` is not an issue in this repository at all. To the outside
#     reader this document is written for, it is a 404.
#
# The failure is the same one issue #441 produced against the I/O list and
# #500 produced against the spec table, in its third venue: a reader who
# cannot re-run anything is handed a reference that no longer means what the
# document says it means. An unmet row whose named owner is closed is not a
# tracked gap; it is an abandoned one, described as tracked.
#
# THE RULES
#
# 1. RESOLVABLE. Every `#N` in a graded document must be an issue or a pull
#    request in *this* repository. Cross-repository issue numbers do not
#    resolve for the reader this document is addressed to, and a bare `#N`
#    gives them no way to discover that.
#
# 2. STATE ANNOTATION. A reference the document annotates with a state --
#    `#N (open)`, `#N (closed)`, `#N is closed`, `#N remains open` -- must
#    match the forge. This is the cheapest claim in the document to leave
#    behind and the one a reader is most likely to act on.
#
# 3. OWNERSHIP. A reference introduced by a present-tense ownership phrase --
#    "tracked at", "tracked by", "filed as", "routed to", "owned at/by",
#    "owed at/by/from" -- must be OPEN. Closed work owns nothing. The phrase
#    in the *past* tense ("was filed as #273", "were tracked at") is exempt:
#    it narrates history, which is exactly what this repository's evidence
#    records are for, and a history that named a then-open issue does not
#    become false when that issue closes. So is a reference the document
#    itself marks closed ("#505, itself closed", "the now-closed #10"): the
#    reader has been told, and rule 2 grades the telling.
#
#    "owed at" and "owned at" were added after they let a stale owner
#    through twice. sim/README.md's campaign table said the random half of
#    period jitter "is owed at **#505**", and sim/CHARACTERIZATION.md said
#    it was "owned at **#505**", for as long as #505 had been closed --
#    because neither file was graded, and neither phrase was one this rule
#    recognised. Both files are graded now.
#
#    signoff/README.md joined the list for the same reason (issue #564): it
#    is the prose beside this block's T1 verdict of record, and it went on
#    naming #427 as the owner of the item-11 gap for days after #427 closed.
#    Adding it also surfaced a bare `(#2057)` -- a klayout-tools commit's PR
#    number, which rule 1 correctly rejects as unresolvable here.
#
# A reference qualified by a sibling repository's name ("klayout-tools
# #309") is a different repository's issue and is not graded here at all;
# resolving it against this repository would grade the wrong issue.
#
# 4. SOURCE-COLUMN STATE. An issue cited in the Source column of the section-5
#    specification table must carry an explicit `(open)` or `(closed)`
#    annotation, so rule 2 can grade it. The document already adopted this
#    convention for the Reference input row; the rule makes it the convention
#    rather than one row's habit.
#
# WHAT IT DOES NOT DO
#
# It grades neither whether a named owner is the *right* owner nor whether an
# open issue is actually being worked. It cannot: both are judgements, and a
# check that guessed at them would be grading its own model of the work.
#
# `spec/pll.md` is deliberately NOT graded, for the reason #500 gave when it
# found the same defect there: that file's Verification-owed table names #13
# for two rows and #12 for one, both closed, and re-pointing a ratified
# specification's own rows is a decision-record act, not an edit a check may
# force. Those are filed rather than fixed here (#499 for #12; see the issue
# filed alongside this check for #13).
#
# THIS IS THE ONE CHECK IN THIS REPOSITORY THAT NEEDS THE FORGE. Every other
# one reads only committed files and is therefore deterministic on a tree.
# This one cannot be: the fact it grades lives on the forge. Two consequences,
# stated rather than hidden:
#
#   - It SKIPS (exit 0) when `gh` is absent, unauthenticated, rate-limited, or
#     otherwise unable to answer. A skip is not a pass, and it says so on
#     stdout. CI runs it with a token so the skip path is the exception.
#   - It can fail a pull request that changed nothing, because someone closed
#     an issue the document cites. That is the intended behaviour and the
#     whole point: the document went stale at that moment, not at the moment
#     someone next edited it.
#
# Usage: docs/lib/check-issue-reference-state.sh
# Exit codes: 0 every reference resolves, every state annotation matches, and
#               every present-tense owner is open (or the forge could not be
#               reached, in which case the check SKIPS and says so),
#             1 a reference does not resolve in this repository, a state
#               annotation contradicts the forge, a present-tense owner is
#               closed, a section-5 Source-column issue carries no state
#               annotation, or a graded file is missing.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

GRADED=(
  "docs/chipalooza/challenge-5-proposal.md"
  "README.md"
  "sim/README.md"
  "sim/CHARACTERIZATION.md"
  "signoff/README.md"
)

if ! command -v python3 >/dev/null 2>&1; then
  echo "FAIL: python3 is not on PATH -- this check could not run, and a" \
    "check that did not run is not a check that passed" >&2
  exit 1
fi

python3 - "${REPO_ROOT}" "${GRADED[@]}" <<'PY'
import os
import re
import subprocess
import sys

repo_root, graded = sys.argv[1], sys.argv[2:]

#: An issue reference as either document writes one. The lookbehind keeps a
#: Markdown heading anchor (`spec/pll.md#lock-time`) out, because there the
#: `#` follows a word character; a `/`-separated list (`#9/#10/#11`) and a
#: compound modifier (`post-#24`) are both deliberately still matched.
REFERENCE = re.compile(r"(?<![\w#])#(\d{1,6})(?!\d)")

#: Words that precede a number which is not an issue number at all. Matched
#: against the token immediately before the `#`. "Epic" is deliberately NOT
#: here: `Epic #542` reads to the outside reader as an issue of this
#: repository, and rule 1 exists to say that it is not one.
NOT_AN_ISSUE = ("challenge", "challenge's")

#: `(open)`, `(closed)`, `is closed`, `remains open`, `-- now fixed and
#: closed` -- the annotation shapes either document uses, taken from the text
#: that immediately follows the reference.
STATE_ANNOTATION = re.compile(
    r"^\s*(?:\**\s*)?"
    r"(?:\(|--\s*|—\s*|,\s*)?\s*"
    r"(?:is\s+|are\s+|remains\s+|stays\s+|now\s+|still\s+|both\s+|itself\s+)*"
    r"(?:fixed\s+and\s+)?"
    r"\**(?P<state>open|closed)\**"
    r"(?=[\s).,;:|*]|$)",
    re.IGNORECASE,
)

#: A present-tense ownership phrase. `was`/`were` in front of it makes it a
#: statement about the past, which rule 3 exempts; so does "previously".
OWNERSHIP = re.compile(
    r"(?<!\bwas\s)(?<!\bwere\s)(?<!\bpreviously\s)"
    r"\b(?:tracked(?:\s+separately)?\s+(?:at|by)|filed\s+as|routed\s+to|"
    r"owned\s+(?:at|by)|owed\s+(?:at|by|from)|raised\s+against)\b",
    re.IGNORECASE,
)

#: Where an ownership phrase's reach ends: a sentence terminator, a table-cell
#: boundary, a blank line, or an em-dash aside. Without this a single
#: "Tracked at" would own every number to the end of the file. The em-dash is
#: in the list because this document uses it exactly as an aside -- "tracked
#: at #297 -- #17, which earlier revisions named, closed on 2026-09-08" hands
#: the work to #297 and mentions #17 as history, and a rule that could not
#: tell those apart would forbid the document from explaining itself.
SPAN_END = re.compile(r"(?<=[.;])\s|\s\|\s|\s[—–]\s|\n\n|$")

#: `was`/`were`/`previously` immediately before the phrase -- the past-tense
#: exemption, checked on the text before the match because Python's
#: lookbehind must be fixed-width and "was tracked separately at" is not.
PAST_TENSE = re.compile(r"\b(?:was|were|had\s+been|previously)\s+$", re.IGNORECASE)

#: "the now-closed #10", "closed issue #13" -- a state annotation written in
#: front of the reference rather than after it. Rule 3 reads it the same way it
#: reads a trailing "(closed)": the document has told its reader the issue is
#: closed, so it is not presenting it as a live owner.
LEADING_CLOSED = re.compile(r"\b(?:now-)?closed\s+(?:issues?\s+)?\**$", re.IGNORECASE)

#: A reference qualified by another repository's name -- "klayout-tools #309".
#: That number is not this repository's #309, and grading it here would
#: resolve it against the wrong issue, so it is not graded at all. The names
#: are listed rather than pattern-matched because a pattern loose enough to
#: find a repository name also finds a hyphenated adjective ("the now-closed
#: #10", "a differently-shaped #12"), which this document uses constantly;
#: these are the two sibling repositories CLAUDE.md sends work to.
FOREIGN_REPO = re.compile(r"(?:\b[\w.-]+/)?\b(?:klayout-tools|gf180-bandgap)\s+$")

#: "issue #13", "issues #496" -- the spelling section 5's Source column uses
#: when it presents an issue as a row's source of record rather than as
#: provenance for a cited record.
SOURCE_ISSUE = re.compile(r"\bissues?\s+$", re.IGNORECASE)

SECTION5 = re.compile(r"^##\s+5\.\s", re.MULTILINE)
SECTION_ANY = re.compile(r"^##\s+\d+\.\s", re.MULTILINE)

failures = []


def fail(message):
    failures.append(message)


def repo_slug():
    """owner/name for this repository, from the environment or the remote."""
    slug = os.environ.get("GH_REPO", "").strip()
    if slug:
        return slug
    try:
        url = subprocess.run(
            ["git", "-C", repo_root, "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.search(r"[:/]([^/:]+/[^/]+?)(?:\.git)?$", url)
    return match.group(1) if match else None


def read(rel):
    path = os.path.join(repo_root, rel)
    if not os.path.isfile(path):
        fail("%s does not exist -- a graded document cannot be missing" % rel)
        return None
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def references(text):
    """[(number, start, end)] for every issue reference in `text`."""
    found = []
    for match in REFERENCE.finditer(text):
        before = text[max(0, match.start() - 24):match.start()]
        word = re.search(r"([A-Za-z']+)\s*$", before)
        if word and word.group(1).casefold() in NOT_AN_ISSUE:
            continue
        if FOREIGN_REPO.search(before):
            continue
        found.append((int(match.group(1)), match.start(), match.end()))
    return found


def owned_spans(text):
    """Character ranges an unexpired present-tense ownership phrase covers."""
    spans = []
    for match in OWNERSHIP.finditer(text):
        if PAST_TENSE.search(text[max(0, match.start() - 24):match.start()]):
            continue
        end = SPAN_END.search(text, match.end())
        spans.append((match.end(), end.start() if end else len(text), match.group(0)))
    return spans


def section5_source_cells(text):
    """Character ranges of the Source column of section 5's spec table."""
    head = SECTION5.search(text)
    if head is None:
        return []
    tail = SECTION_ANY.search(text, head.end())
    stop = tail.start() if tail else len(text)
    cells = []
    for line in re.finditer(r"^\|.*\|\s*$", text[head.start():stop], re.MULTILINE):
        row = line.group(0)
        if re.fullmatch(r"\|[\s:|-]+\|", row.strip()):
            continue
        bars = [m.start() for m in re.finditer(r"(?<!\\)\|", row)]
        if len(bars) < 3:
            continue
        base = head.start() + line.start()
        cells.append((base + bars[-2] + 1, base + bars[-1]))
    return cells


class Forge:
    """Issue state lookups, memoised, with one honest failure mode."""

    def __init__(self, slug):
        self.slug = slug
        self.cache = {}
        self.unreachable = None

    def state(self, number):
        """'open', 'closed', 'missing', or None when the forge cannot answer."""
        if number in self.cache:
            return self.cache[number]
        try:
            result = subprocess.run(
                ["gh", "api", "repos/%s/issues/%d" % (self.slug, number),
                 "--jq", ".state"],
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            self.unreachable = str(exc)
            return None
        text = (result.stdout or "").strip()
        if result.returncode == 0 and text in ("open", "closed"):
            self.cache[number] = text
            return text
        combined = (result.stdout or "") + (result.stderr or "")
        if "Not Found" in combined or "HTTP 404" in combined:
            self.cache[number] = "missing"
            return "missing"
        self.unreachable = combined.strip().splitlines()[0] if combined.strip() else \
            "gh exited %d with no output" % result.returncode
        return None


slug = repo_slug()
if slug is None:
    print("SKIP: could not determine this repository's owner/name, so no issue "
          "reference could be graded. A skip is not a pass.")
    sys.exit(0)

forge = Forge(slug)
graded_text = {}
for rel in graded:
    text = read(rel)
    if text is not None:
        graded_text[rel] = text

if failures:
    for message in failures:
        sys.stderr.write("FAIL: %s\n" % message)
    sys.exit(1)

checked = 0
for rel, text in graded_text.items():
    spans = owned_spans(text)
    sources = section5_source_cells(text) if rel.endswith("challenge-5-proposal.md") else []
    for number, start, end in references(text):
        state = forge.state(number)
        if state is None:
            print("SKIP: the forge could not be read (%s), so no issue reference "
                  "was graded. A skip is not a pass." % forge.unreachable)
            sys.exit(0)
        checked += 1
        line = text.count("\n", 0, start) + 1
        where = "%s:%d" % (rel, line)

        # Rule 1 -- resolvable.
        if state == "missing":
            fail("%s references #%d, which is not an issue or pull request in "
                 "%s. An outward-facing document's reader cannot resolve a "
                 "number from another repository" % (where, number, slug))
            continue

        # Rule 2 -- state annotation.
        annotation = STATE_ANNOTATION.match(text[end:end + 40])
        if annotation and annotation.group("state").casefold() != state:
            fail("%s says #%d is %s; the forge says it is %s"
                 % (where, number, annotation.group("state").casefold(), state))

        # Rule 3 -- ownership. A compound modifier (`post-#24 charge pump`)
        # names a state of the design, not an owner of the work, so a
        # reference glued to the preceding word by a hyphen is exempt.
        # A reference the document itself marks closed -- "#505, itself
        # closed", "the now-closed #10" -- is narrated, not handed work.
        self_marked_closed = (
            (annotation and annotation.group("state").casefold() == "closed")
            or LEADING_CLOSED.search(text[max(0, start - 24):start])
        )
        if state == "closed" and not text[start - 1:start] == "-" \
                and not self_marked_closed:
            for span_start, span_end, phrase in spans:
                if span_start <= start < span_end:
                    fail("%s hands work to #%d with \"%s\", but #%d is closed. "
                         "Closed work owns nothing -- name an open issue or say "
                         "plainly that the gap is unowned"
                         % (where, number, phrase.strip(), number))
                    break

        # Rule 4 -- source-column state. Scoped to a reference the cell
        # introduces as a source of record ("issue #499 (open)"); a bare
        # `#N` inside that cell's prose is provenance for a record ("the
        # wrap-safe gate of #273"), not a claim about who owns a gap.
        named_as_issue = SOURCE_ISSUE.search(text[max(0, start - 12):start])
        if named_as_issue and any(
            cell_start <= start < cell_end for cell_start, cell_end in sources
        ):
            if not annotation:
                fail("%s cites #%d in section 5's Source column with no (open) "
                     "or (closed) annotation, so rule 2 cannot grade it and a "
                     "reader cannot tell whether the gap is still owned"
                     % (where, number))

if failures:
    for message in failures:
        sys.stderr.write("FAIL: %s\n" % message)
    sys.stderr.write("FAIL: %d issue-reference problem(s) in %s\n"
                     % (len(failures), ", ".join(graded)))
    sys.exit(1)

print("OK: %d issue reference(s) across %s resolve in %s, and every state "
      "annotation and present-tense owner agrees with the forge."
      % (checked, ", ".join(graded), slug))
sys.exit(0)
PY
