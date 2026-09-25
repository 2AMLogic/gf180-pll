#!/usr/bin/env bash
#
# Fails if what a document says about how the closed-loop testbenches drive the
# four charge-pump bias references -- `IBN`, `ICN`, `IBP`, `ICP` -- is not what
# the committed decks do, or if it attributes a quotation to evidence records
# that do not contain it.
#
# WHY THIS EXISTS (issue #237)
#
# The PLL has no bias generator. Every closed-loop deck drives the four bias
# pins from ideal current sources, and docs/chipalooza/challenge-5-proposal.md
# turns that into two things an outside reader acts on: section 4's bring-up
# step tells a bench operator what current to supply into which pin, and
# section 2.2's pad table tells the Challenge why this block asks for four
# current references rather than two. Both are stated as transcriptions of
# evidence, with the evidence cited. Neither was graded, and on 2026-09-25
# both citations were wrong:
#
#   * Section 4 step 1 sent the reader to `.param iunit=8u` in
#     `sim/lock-time/testbench/tb_lock_time.sp`. That deck contains no such
#     line: it declares the parameter and leaves the value to its run.sh
#     (`IUNIT=8u`), which passes it on the command line. The number was right;
#     the place a reader was told to look for it was not, and a reader who
#     looked would have found nothing.
#   * Section 2.2's IBN/ICN/IBP/ICP row quoted "a separate, unbuilt block" and
#     said every closed-loop evidence record's own Limitations field says so
#     verbatim. Seven of the thirty-five closed-loop records do. The other
#     twenty-eight -- all of sim/lock-time, sim/output-range, sim/period-jitter
#     and sim/reference-spur -- never mention a bias generator at all.
#
# THE RULES
#
# The check first enumerates the CLOSED-LOOP DECKS: every committed deck under
# `sim/*/testbench*/` that drives all four bias ports from independent current
# sources, in a campaign whose testbench composes the assembled PLL (a file in
# it names `design/netlist/pll_top.spice` or sources `sim/lib/pll_top_dut.sh`).
# Charge-pump-only decks drive the same ports but are not closed-loop, and are
# out of scope. For each source it RESOLVES the current the deck actually runs
# with, and remembers WHERE that value is set: a literal on the source line, a
# `.param` in the deck, a `params` entry in the campaign's `tb.json`, or a shell
# assignment in a testbench script that passes the parameter to ngspice
# (`"iunit=${IUNIT}"` ... `IUNIT=8u`). A deck the scan cannot resolve fails:
# a parser that resolves nothing must not look like a clean tree.
#
# A document makes a DRIVE CLAIM wherever one paragraph, list item or table
# row states "<N> µA every closed-loop record". Inside that same unit:
#
# 1. CITED CAMPAIGNS RUN AT THE STATED CURRENT. Every `sim/...` path the unit
#    cites stands for its campaign. Each such campaign must have at least one
#    closed-loop deck, and every bias source in every one of them must resolve
#    to the stated current.
#
# 2. A CITED PATH IS WHERE THE VALUE IS SET. When the unit quotes the setting
#    itself (`.param iunit=8u`, `IUNIT=8u`), every path it cites must be a
#    place a reader can find one of those settings for the decks it stands
#    for: a deck path must set the value in that deck; a script path must be
#    the file the value comes from for at least one deck; a campaign directory
#    must set it, somewhere inside it, by a line that is one of the quoted
#    settings. And every quoted setting must itself state the stated current.
#    This is the rule the tb_lock_time.sp citation fails.
#
# 3. QUOTED SOURCE LINES ARE THE DECKS' OWN. A quoted source line (`iibn vdd
#    ibn`) must open a line in every closed-loop deck of every cited campaign.
#    Where the unit also says which pins are "sourced into" the die and which
#    are "sunk out of" it, every closed-loop deck in the repository must point
#    each source that way: into the named pin for the first set, out of it to
#    ground for the second.
#
# 4. "EVERY CLOSED-LOOP RECORD" MEANS EVERY ONE. The stated current must be the
#    current of every bias source in every closed-loop deck in the repository,
#    cited or not. A new closed-loop campaign at another current makes the
#    sentence false the day it lands, whether or not anyone edits it.
#
# And separately, for quotations:
#
# 5. A VERBATIM QUOTATION IS IN WHAT IT IS ATTRIBUTED TO. A sentence that says
#    something is quoted "verbatim" and carries a double-quoted phrase is
#    graded against the records it names: every `sim/<campaign>/records/*.md`
#    path in the sentence, and -- if the sentence attributes the phrase to
#    "every closed-loop ... record" -- every record of every campaign that has
#    a closed-loop deck. Each must contain the phrase (whitespace-normalised;
#    records wrap lines). A sentence that names no record and makes no
#    universal attribution is not graded: there is nothing to look in.
#
# WHAT IT DOES NOT DO
#
# It does not run ngspice or read a record's measured currents; it grades the
# decks as committed, which is what a record freezes. It does not grade the
# "4x the unit-leg current" ratio section 2.2 and the records state -- that is a
# claim about the charge pump's mirror geometry (design/README.md), not about
# the testbench, and grading it needs the device sizes. It grades only the
# graded documents below: design/README.md describes the same drive in prose
# with no citation to grade it against. And rule 5 grades that a phrase is
# present in a record, not that it sits in the record's Limitations field
# rather than elsewhere in it -- the records have no single machine-readable
# Limitations boundary to anchor on.
#
# Usage: sim/lib/check-bias-drive-claims.sh
# Exit codes: 0 every drive claim's current, cited setting sites and quoted
#               source lines match the closed-loop decks, and every verbatim
#               quotation is in every record it is attributed to;
#             1 a cited campaign has no closed-loop deck or runs another
#               current, a cited path does not set the value it is cited for,
#               a quoted setting states another current, a quoted source line
#               or stated polarity disagrees with a deck, a closed-loop deck
#               anywhere runs another current, a quotation is missing from a
#               record it is attributed to, a graded document is missing, or
#               the deck scan found or resolved nothing (a broken parser must
#               not look like a clean tree).

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# The documents that make, or could make, the drive claim. The proposal is the
# one that does today; README.md and sim/CHARACTERIZATION.md are graded so the
# claim cannot be restated there ungraded.
GRADED=(
  "README.md"
  "sim/CHARACTERIZATION.md"
  "docs/chipalooza/challenge-5-proposal.md"
)

if ! command -v python3 >/dev/null 2>&1; then
  echo "FAIL: python3 is not on PATH -- this check could not run, and a" \
    "check that did not run is not a check that passed" >&2
  exit 1
fi

python3 - "${REPO_ROOT}" "${GRADED[@]}" <<'PY'
import glob
import json
import os
import re
import sys

repo_root, graded = sys.argv[1], sys.argv[2:]

DECK_GLOBS = ("sim/*/testbench*/*.sp", "sim/*/testbench*/*.spice")
PORTS = ("ibn", "icn", "ibp", "icp")
PORT_NODE = re.compile(r"^(ibn|icn|ibp|icp)(?:_\w+)?$", re.IGNORECASE)
GROUND = {"0", "vss", "gnd", "gnd_vco"}

# `iibn vdd ibn dc 'iunit'` -- instance, n+, n-, the rest.
CURRENT_SOURCE = re.compile(r"^\s*(i\w*)\s+(\S+)\s+(\S+)\s+(.*)$", re.IGNORECASE)

# What marks a campaign as composing the assembled PLL.
COMPOSES_TOP = ("design/netlist/pll_top.spice", "pll_top_dut.sh")

INLINE_CODE = re.compile(r"`([^`\n]+)`")
SIM_PATH = re.compile(r"^sim/([\w.-]+)(?:/[\w./-]*)?$")
RECORD_PATH = re.compile(r"^sim/([\w.-]+)/records/[\w.-]+\.md$")
PARAM_SETTING = re.compile(r"^\.param\s+(\w+)\s*=\s*(\S+)$", re.IGNORECASE)
SHELL_SETTING = re.compile(r"^(?:export\s+)?([A-Za-z_]\w*)=(\S+)$")
QUOTED_SOURCE = re.compile(r"^(i\w*)\s+(\S+)\s+(\S+)$", re.IGNORECASE)

DRIVE_CLAIM = re.compile(
    r"(\d+(?:\.\d+)?)\s*[µu]A\s+every\s+closed-loop\s+(?:`?[\w/]+`?\s+)?records?",
    re.IGNORECASE,
)
UNIVERSAL_RECORDS = re.compile(
    r"every\s+closed-loop\s+(?:`?[\w/-]+`?\s+){0,2}records?\b", re.IGNORECASE
)
QUOTATION = re.compile(r"\"([^\"\n]{4,}?)\"|“([^”\n]{4,}?)”")
SOURCED = re.compile(
    r"((?:`\w+`(?:\s*,\s*|\s+and\s+)?)+)\s+are\s+sourced\s+\*?into\b", re.IGNORECASE
)
SUNK = re.compile(
    r"((?:`\w+`(?:\s*,\s*|\s+and\s+)?)+)\s+are\s+sunk\s+\*?out\s+of\b", re.IGNORECASE
)

SUFFIX = {
    "f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3,
    "k": 1e3, "meg": 1e6, "g": 1e9, "t": 1e12,
}
NUMBER = re.compile(r"^([+-]?\d+(?:\.\d*)?(?:e[+-]?\d+)?)(meg|[fpnumkgt])?[a-z]*$",
                    re.IGNORECASE)


def spice_value(text):
    text = text.strip().strip("'\"{}")
    m = NUMBER.match(text)
    if not m:
        return None
    return float(m.group(1)) * SUFFIX.get((m.group(2) or "").lower(), 1.0)


def same(a, b):
    return a is not None and b is not None and abs(a - b) <= 1e-9 * max(abs(a), abs(b))


def fmt(v):
    return "%g µA" % (v * 1e6)


def read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        return ""


def campaign_of(rel):
    parts = rel.split("/")
    return parts[1] if len(parts) > 1 and parts[0] == "sim" else None


def testbench_files(campaign):
    out = []
    for d in sorted(glob.glob(os.path.join(repo_root, "sim", campaign, "testbench*"))):
        for dirpath, _dirs, files in os.walk(d):
            for name in sorted(files):
                out.append(os.path.join(dirpath, name))
    return out


def rel(path):
    return os.path.relpath(path, repo_root)


fail_count = 0


def fail(msg):
    global fail_count
    fail_count += 1
    sys.stderr.write("FAIL: " + msg.rstrip() + "\n")


# ----------------------------------------------------------- resolution
def resolve(param, deck_path):
    """Where does `param` get its value for `deck_path`?

    Returns (value, source-file-relpath, setting) where setting is
    (kind, name, value-text), or None if nothing sets it.
    """
    deck_dir = os.path.dirname(deck_path)
    # 1. a `.param` in the deck itself
    for line in read(deck_path).splitlines():
        s = line.strip()
        if not s.lower().startswith(".param"):
            continue
        body = re.sub(r"\s*=\s*", "=", s[len(".param"):])
        for tok in body.split():
            if "=" in tok:
                name, val = tok.split("=", 1)
                if name.lower() == param.lower():
                    return spice_value(val), rel(deck_path), (".param", name.lower(), val)
    # 2. the campaign manifest's params
    manifest = os.path.join(deck_dir, "tb.json")
    if os.path.isfile(manifest):
        try:
            params = json.loads(read(manifest)).get("params") or {}
        except ValueError:
            params = {}
        for name, val in params.items():
            if name.lower() == param.lower():
                return spice_value(str(val)), rel(manifest), ("json", name.lower(), str(val))
    # 3. a testbench script that passes `param=${VAR}` and assigns VAR
    passes = re.compile(r"\b%s=\$\{?(\w+)\}?" % re.escape(param), re.IGNORECASE)
    scripts = [p for p in sorted(glob.glob(os.path.join(deck_dir, "*.sh")))]
    for script in scripts:
        text = read(script)
        for var in passes.findall(text):
            assign = re.compile(r"^\s*(?:export\s+)?%s=(\S+?)\s*$" % re.escape(var), re.MULTILINE)
            m = assign.search(text)
            if m:
                val = m.group(1).strip("'\"")
                return spice_value(val), rel(script), ("sh", var, val)
    return None


decks = {}  # rel -> {"campaign", "sources": [(inst, np, nn, port, value, src_rel, setting)], "lines"}
for pattern in DECK_GLOBS:
    for path in sorted(glob.glob(os.path.join(repo_root, pattern))):
        r = rel(path)
        if "/netlist-snapshots/" in r:
            continue
        sources = []
        lines = []
        for line in read(path).splitlines():
            if line.lstrip().startswith("*"):
                continue
            m = CURRENT_SOURCE.match(line)
            if not m:
                continue
            inst, np_, nn, rest = m.groups()
            port = None
            for node in (nn, np_):
                pm = PORT_NODE.match(node)
                if pm:
                    port = pm.group(1).lower()
                    break
            if port is None:
                continue
            lines.append(" ".join(line.split()).lower())
            toks = rest.split()
            if toks and toks[0].lower() == "dc":
                toks = toks[1:]
            expr = toks[0] if toks else ""
            literal = spice_value(expr)
            if literal is not None:
                sources.append((inst, np_, nn, port, literal, r, ("literal", inst.lower(), expr)))
                continue
            name = expr.strip("'\"{}")
            found = resolve(name, path) if re.match(r"^\w+$", name) else None
            if found is None:
                sources.append((inst, np_, nn, port, None, None, ("unresolved", name, expr)))
            else:
                val, src, setting = found
                sources.append((inst, np_, nn, port, val, src, setting))
        if {s[3] for s in sources} == set(PORTS):
            decks[r] = {"campaign": campaign_of(r), "sources": sources, "lines": lines}

composing = set()
for campaign in sorted({d["campaign"] for d in decks.values()}):
    for f in testbench_files(campaign):
        text = read(f)
        if any(marker in text for marker in COMPOSES_TOP):
            composing.add(campaign)
            break

closed = {r: d for r, d in decks.items() if d["campaign"] in composing}
closed_campaigns = sorted({d["campaign"] for d in closed.values()})

if not closed:
    fail("found no closed-loop deck (all four of %s driven by current sources, in a "
         "campaign composing pll_top) under %s -- enumeration is broken, and a parser "
         "that reads nothing must not look like a clean tree"
         % ("/".join(PORTS), " / ".join(DECK_GLOBS)))
    sys.exit(1)

for r, d in sorted(closed.items()):
    for inst, _np, _nn, _port, val, _src, setting in d["sources"]:
        if val is None:
            fail("%s: cannot resolve the current `%s` runs with (`%s`): no literal, no "
                 "`.param`, no tb.json params entry and no testbench script assigns it. "
                 "A value this check cannot find is a value it cannot grade."
                 % (r, inst, setting[2]))
if fail_count:
    sys.exit(1)


def units_of(text):
    """Paragraphs, list items and table rows, each whitespace-joined."""
    units, cur = [], []
    for line in text.splitlines():
        starts = (not line.strip()) or line.lstrip().startswith("|") or \
            re.match(r"^\s*(?:\d+\.|[-*])\s", line)
        if starts and cur:
            units.append(" ".join(" ".join(cur).split()))
            cur = []
        if line.strip():
            cur.append(line)
            if line.lstrip().startswith("|"):
                units.append(" ".join(line.split()))
                cur = []
    if cur:
        units.append(" ".join(" ".join(cur).split()))
    return units


def sentences_of(unit):
    return re.split(r"(?<=[.;])\s+(?=[A-Z(*—-])|\s+—\s+", unit)


def settings_equal(quoted, setting):
    kind, name, val = setting
    qkind, qname, qval = quoted
    if qkind == ".param":
        ok_kind = kind == ".param"
    else:
        ok_kind = kind == "sh"
    return ok_kind and qname.lower() == name.lower() and same(spice_value(qval), spice_value(val))


def show(setting):
    kind, name, val = setting
    if kind == ".param":
        return "`.param %s=%s`" % (name, val)
    if kind == "sh":
        return "`%s=%s`" % (name, val)
    if kind == "json":
        return "tb.json params `\"%s\": \"%s\"`" % (name, val)
    return "a literal `%s`" % val


drive_claims = 0
quotations = 0
records_read = 0

for doc in graded:
    doc_path = os.path.join(repo_root, doc)
    if not os.path.isfile(doc_path):
        fail("%s does not exist" % doc)
        continue
    text = read(doc_path)

    for unit in units_of(text):
        spans = INLINE_CODE.findall(unit)

        # ---------------------------------------------------- rule 5
        for sentence in sentences_of(unit):
            if not re.search(r"\bverbatim\b", sentence, re.IGNORECASE):
                continue
            phrases = [a or b for a, b in QUOTATION.findall(sentence)]
            if not phrases:
                continue
            targets = set()
            for span in INLINE_CODE.findall(sentence):
                m = RECORD_PATH.match(span.strip())
                if m:
                    targets.add(span.strip())
            universal = bool(UNIVERSAL_RECORDS.search(sentence))
            if universal:
                for c in closed_campaigns:
                    for p in sorted(glob.glob(os.path.join(repo_root, "sim", c, "records", "*.md"))):
                        targets.add(rel(p))
            if not targets:
                continue
            for phrase in phrases:
                quotations += 1
                want = " ".join(phrase.split())
                missing = []
                for t in sorted(targets):
                    body = read(os.path.join(repo_root, t))
                    records_read += 1
                    if not body:
                        missing.append((t, "does not exist"))
                    elif want not in " ".join(body.split()):
                        missing.append((t, "does not contain it"))
                if missing:
                    fail("%s quotes \"%s\" and attributes it verbatim to %s, but %d of the "
                         "%d record(s) that attribution covers do not say it:\n%s"
                         "Name the records that do, rather than the class they belong to.\n"
                         % (doc, want,
                            "every closed-loop record" if universal else "the records it names",
                            len(missing), len(targets),
                            "".join("    %s  (%s)\n" % m for m in missing)))

        # ---------------------------------------------------- drive claims
        m = DRIVE_CLAIM.search(unit)
        if not m:
            continue
        drive_claims += 1
        stated = float(m.group(1)) * 1e-6

        cited = []
        for span in spans:
            s = span.strip()
            if not SIM_PATH.match(s) or RECORD_PATH.match(s) or \
                    not os.path.exists(os.path.join(repo_root, s)):
                continue
            # A path is a campaign citation only if it is inside a campaign;
            # `sim/lib/...` (this check, the harness) is not one.
            if not glob.glob(os.path.join(repo_root, "sim", campaign_of(s), "testbench*")):
                continue
            cited.append(s.rstrip("/"))
        cited_campaigns = sorted({campaign_of(p) for p in cited})

        quoted_settings = []
        quoted_sources = []
        for span in spans:
            s = " ".join(span.split())
            pm = PARAM_SETTING.match(s)
            if pm:
                quoted_settings.append((".param", pm.group(1), pm.group(2)))
                continue
            sm = SHELL_SETTING.match(s)
            if sm and not s.startswith("sim/"):
                quoted_settings.append(("sh", sm.group(1), sm.group(2)))
                continue
            qm = QUOTED_SOURCE.match(s)
            if qm and any(PORT_NODE.match(n) for n in qm.groups()[1:]):
                quoted_sources.append(s.lower())

        # ------------------------------------------------ rule 1
        for c in cited_campaigns:
            mine = {r: d for r, d in closed.items() if d["campaign"] == c}
            if not mine:
                fail("%s cites `sim/%s` for the %s its closed-loop records drive the bias "
                     "pins with, but that campaign has no closed-loop deck -- nothing in it "
                     "drives %s against the assembled PLL.\n"
                     % (doc, c, fmt(stated), "/".join(p.upper() for p in PORTS)))
                continue
            for r, d in sorted(mine.items()):
                for inst, _np, _nn, _port, val, src, setting in d["sources"]:
                    if not same(val, stated):
                        fail("%s states %s for the bias pins and cites `sim/%s`, but `%s` in "
                             "%s runs at %s (%s in %s).\n"
                             % (doc, fmt(stated), c, inst, r, fmt(val), show(setting), src))

        # ------------------------------------------------ rule 2
        for q in quoted_settings:
            if not same(spice_value(q[2]), stated):
                fail("%s states %s for the bias pins but quotes the setting %s, which is %s.\n"
                     % (doc, fmt(stated), show(q), fmt(spice_value(q[2])) if spice_value(q[2]) is not None else "not a number"))
        if quoted_settings:
            for p in cited:
                c = campaign_of(p)
                full = os.path.join(repo_root, p)
                if os.path.isdir(full):
                    standing = {r: d for r, d in closed.items() if d["campaign"] == c}
                    for r, d in sorted(standing.items()):
                        bad = [s for s in d["sources"]
                               if not any(settings_equal(q, s[6]) for q in quoted_settings)]
                        if bad:
                            inst, _np, _nn, _port, _val, src, setting = bad[0]
                            fail("%s cites `%s` as where %s is set, but %s's `%s` gets its "
                                 "value from %s in %s -- not one of the settings the document "
                                 "quotes (%s). A reader told to look for it there will not "
                                 "find it.\n"
                                 % (doc, p, " or ".join(show(q) for q in quoted_settings),
                                    r, inst, show(setting), src,
                                    ", ".join(show(q) for q in quoted_settings)))
                elif p in closed:
                    d = closed[p]
                    bad = [s for s in d["sources"]
                           if s[5] != p or not any(settings_equal(q, s[6]) for q in quoted_settings)]
                    if bad:
                        inst, _np, _nn, _port, _val, src, setting = bad[0]
                        fail("%s cites `%s` as where %s is set, but that deck sets no such "
                             "value: `%s` gets it from %s in %s. Cite the file that sets it.\n"
                             % (doc, p, " or ".join(show(q) for q in quoted_settings),
                                inst, show(setting), src))
                else:
                    fed = [(r, s) for r, d in closed.items() for s in d["sources"]
                           if s[5] == p and any(settings_equal(q, s[6]) for q in quoted_settings)]
                    if not fed:
                        fail("%s cites `%s` as where %s is set, but it is not where any "
                             "closed-loop deck's bias current comes from.\n"
                             % (doc, p, " or ".join(show(q) for q in quoted_settings)))

        # ------------------------------------------------ rule 3
        for qs in quoted_sources:
            for c in cited_campaigns:
                for r, d in sorted(closed.items()):
                    if d["campaign"] != c:
                        continue
                    if not any(line == qs or line.startswith(qs + " ") for line in d["lines"]):
                        fail("%s quotes `%s` as the closed-loop decks' own source line, but "
                             "%s (cited via `sim/%s`) has no line opening that way.\n"
                             % (doc, qs, r, c))
        for regex, direction in ((SOURCED, "into"), (SUNK, "out of")):
            pm = regex.search(unit)
            if not pm:
                continue
            pins = {p.lower() for p in re.findall(r"`(\w+)`", pm.group(1))}
            for r, d in sorted(closed.items()):
                for inst, np_, nn, port, _val, _src, _setting in d["sources"]:
                    if port not in pins:
                        continue
                    if direction == "into":
                        ok = PORT_NODE.match(nn) is not None
                    else:
                        ok = PORT_NODE.match(np_) is not None and nn.lower() in GROUND
                    if not ok:
                        fail("%s says `%s` is sourced %s the die, but %s's `%s %s %s` points "
                             "the other way.\n"
                             % (doc, port.upper(), direction, r, inst, np_, nn))

        # ------------------------------------------------ rule 4
        for r, d in sorted(closed.items()):
            for inst, _np, _nn, _port, val, src, setting in d["sources"]:
                if not same(val, stated):
                    fail("%s says %s is what every closed-loop record drives the bias pins "
                         "with, but %s's `%s` runs at %s (%s in %s).\n"
                         % (doc, fmt(stated), r, inst, fmt(val), show(setting), src))

if fail_count:
    sys.exit(1)

print(
    "OK: %d closed-loop deck(s) across %d campaign(s) drive %s from current sources, "
    "every value resolved; %d drive claim(s) match the decks they cite and every "
    "deck they do not; %d verbatim quotation(s) found in all %d record read(s) they "
    "are attributed to"
    % (len(closed), len(closed_campaigns), "/".join(p.upper() for p in PORTS),
       drive_claims, quotations, records_read)
)
PY
