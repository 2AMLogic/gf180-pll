#!/usr/bin/env bash
#
# Fails if a committed evidence record was taken on a netlist snapshot that
# could not deliver a configuration pin the record's own committed logs show
# being driven -- unless that record is named in the DISCLOSED table below
# against a decision record that states the effective configuration.
#
# WHY THIS EXISTS (issue #557, following #515)
#
# `design/pll_top.sch` placed the `LDT3` lock-detector trim label off the
# `XLD` instance's real `LDT3` pin, so the exported `pll_top` netlist wired
# that terminal to an xschem auto-named net (`net1`) instead of to the
# declared port. A deck could drive the `ldt3` pad and nothing inside the
# subcircuit read it: the detector saw `code & 0b0111`. DR-026 (#515) found
# that, fixed the schematic, and added `design/lib/check-port-connectivity.sh`
# so the defect cannot recur in `design/`.
#
# What DR-026 could not do is decide which already-committed EVIDENCE was
# taken on the broken export. Its audit was a text grep,
# `grep -rl 'ldt3_code=1' sim/*/corners/*/`, and it returned exactly the five
# logs of the one record DR-026 withdrew a verdict from. That read as
# exhaustive and was not. Three `sim/reference-phase-transfer` records (#509,
# DR-027) had been run that same morning on the same pre-fix export, while
# programming trim code 8 -- MSB set, so the detector ran at code 0 -- and
# reached `main` after DR-026 merged. The grep cannot see them **and never
# could have**: their decks take the trim code from `testbench/tb.json`
# through the harness rather than from a `.param ldt3_code=` line, so the
# string `ldt3_code=1` appears nowhere in their logs. The defect was fully
# visible in those logs the whole time -- as `ldt3` at the rail and
# `xdut.net1` at 0 V in the same operating-point table -- just not as that
# string.
#
# A grep for the way one campaign happened to spell a parameter is not an
# audit of the tree. This check grades the artifacts instead.
#
# THE RULE
#
# For every committed `sim/*/netlist-snapshots/*.spice`:
#
# 1. Parse the snapshot's own `.subckt` blocks and instance lines and find
#    every xschem auto-named `net<N>` with exactly ONE connection in the whole
#    file -- the #515 signature, and the same signature
#    `design/lib/check-port-connectivity.sh` rule 2 grades `design/` on. Map
#    that single connection back through the instantiated subcircuit's own
#    port list to the PORT NAME it stands in for (`LDT3`). That port is dead
#    in this snapshot: it is declared, and the parent wires it to nothing.
#
# 2. Resolve the snapshot to the record it froze (its filename's
#    `<date>-<time>-<sha>` stem) and read that record's committed per-corner
#    logs. If any log's DC operating-point table shows the matching pad node
#    (`ldt3`, the lower-cased port name) driven above PAD_DRIVEN_V, the run
#    drove a pin its own netlist could not deliver -- so the value the design
#    saw is not the value the record states it programmed.
#
# 3. Such a record must appear in DISCLOSED below, mapped to a decision record
#    that exists, is more than a stub, and names the campaign back. As in
#    `sim/lib/check-ref-drive-claims.sh` rule 5, editing a table in a CI
#    script and landing a ratified decision record is a deliberate act with a
#    reviewer in front of it; an environment variable or a dropped file is
#    not, so neither is offered. A disclosed record is still counted and still
#    named in the summary -- the allowance buys "this is accounted for", never
#    "this is invisible".
#
# A snapshot that carries a dead port whose pad NO committed log drives is
# reported and passes: `sim/lock-window-proxy`'s record is on the same pre-fix
# export but drives `delaywin_3v3` directly, never through the `pll_top` trim
# port, so nothing it measured passed through the missing wire. That
# distinction is made from the record's own logs rather than from a reader's
# assurance.
#
# WHY BOTH HALVES ARE NEEDED
#
# The snapshot alone over-reports (a dead port nobody drove changed nothing).
# The log alone under-reports: `ldt3` at the rail is unremarkable on a netlist
# where `LDT3` is wired, which is every post-DR-026 record. It is the PAIR --
# this pin is driven, and in this exact frozen netlist it goes nowhere -- that
# is the defect, and both halves of it are frozen artifacts of the run rather
# than mutable manifests. `testbench/tb.json` is deliberately not consulted:
# it is edited after a record is written (DR-027 SS Errata does exactly that),
# so a check that read today's manifest would grade yesterday's run against a
# configuration it never ran.
#
# WHAT IT DOES NOT DO
#
# It does not run ngspice and does not know what a pin is SUPPOSED to be. It
# cannot see a run whose campaign committed no netlist snapshot, and it says
# so in its summary rather than counting such a campaign as clean. And, like
# `design/lib/check-port-connectivity.sh`, it is blind to a port wired to the
# WRONG place rather than to nothing: a mis-wired net with two connections has
# no auto-named single-connection signature.
#
# Usage: sim/lib/check-record-trim-connectivity.sh
# Exit codes: 0 no committed record drove a pin its own frozen netlist
#               snapshot leaves dead, or every record that did is disclosed in
#               a named decision record;
#             1 an undisclosed record did, a named decision record is missing
#               or is a stub or does not name its campaign, or this check
#               could not parse a file it was asked to grade (a check that did
#               not run is not a check that passed).

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "FAIL: python3 is not on PATH -- this check could not run, and a" \
    "check that did not run is not a check that passed" >&2
  exit 1
fi

python3 - "${REPO_ROOT}" <<'PY'
import glob
import os
import re
import sys

repo_root = sys.argv[1]

#: A record that drove a dead pin is admitted ONLY through this table, which
#: maps (campaign, record id) to the decision record stating what the run
#: actually configured. Both entries below are the #515 defect reaching
#: committed evidence; neither is a relaxation, and both decision records
#: withdraw or re-scope what the affected evidence is entitled to say.
DISCLOSED = {
    # DR-026's own subject: the `ff` cell programmed code 11 and ran at
    # code 3. Its crossing verdict is withdrawn there, pending #437.
    ("supply-sensitivity", "20260920-180604-0f91a9b"): (
        "spec/decision-records/"
        "DR-026-lock-detector-trim-msb-unconnected-what-the-ff-cell-measured.md"
    ),
    # #557: all three `reference-phase-transfer` records programmed code 8
    # and ran the detector at code 0. The measured 20*log10(N) transfer is
    # untouched (the trim pins do not reach the signal path it measures);
    # what DR-027 Amendment A1 re-scopes is its lock-assertion remark.
    ("reference-phase-transfer", "20260925-073001-ed38ff1"): (
        "spec/decision-records/"
        "DR-027-reference-phase-transfer-measures-the-exclusions-transfer.md"
    ),
    ("reference-phase-transfer", "20260925-074549-1f4b734"): (
        "spec/decision-records/"
        "DR-027-reference-phase-transfer-measures-the-exclusions-transfer.md"
    ),
    ("reference-phase-transfer", "20260925-080736-b722f33"): (
        "spec/decision-records/"
        "DR-027-reference-phase-transfer-measures-the-exclusions-transfer.md"
    ),
}

#: A decision record short enough to be a placeholder is not a disclosure.
#: The same floor `check-ref-drive-claims.sh` uses for its REARGUED table.
DISCLOSURE_MIN_BYTES = 1500

#: A static configuration pad is "driven" above this. The rails in this
#: repository are 2.97 / 3.30 / 3.63 V and a de-asserted pad reads 0 V or a
#: few nanovolts, so anything in between is neither and is reported as
#: driven rather than silently ignored.
PAD_DRIVEN_V = 0.5

SUBCKT_RE = re.compile(r"^\.subckt\s+(\S+)\s*(.*)$", re.I)
INSTANCE_RE = re.compile(r"^[Xx]\S+")
AUTO_NET_RE = re.compile(r"^net\d+$")
RECORD_ID_RE = re.compile(r"^(\d{8}-\d{6}-[0-9A-Za-z]+)")
#: ngspice's operating-point dump: `<node><spaces><value>`, one per line.
OP_ROW_RE = re.compile(r"^\s*(\S+)\s+([-+0-9.eE]+)\s*$")

failed = False
unparsed = []
hierarchyless = []
unnamed = []


def join_continuations(lines, start):
    """Join ``lines[start]`` with every following ``+``-continuation line."""
    text = lines[start].rstrip("\n")
    i = start + 1
    while i < len(lines) and lines[i].startswith("+"):
        text += " " + lines[i][1:].rstrip("\n")
        i += 1
    return text, i


def instance_nodes(logical_line):
    """The node tokens ``logical_line`` connects, and the model it names.

    ``Xname node1 ... nodeN modelname [param=value ...]`` -- the model name is
    the token before the first ``key=value``, or the last token when there are
    none.
    """
    tokens = logical_line.split()[1:]
    if not tokens:
        return [], None
    param_idx = next((i for i, t in enumerate(tokens) if "=" in t), None)
    model_idx = (param_idx - 1) if param_idx is not None else len(tokens) - 1
    if model_idx <= 0:
        return [], None
    return tokens[:model_idx], tokens[model_idx]


def dead_ports(rel):
    """Every (child subckt, port name, auto-named net) left dead in a file.

    "Dead" is the #515 signature exactly: an xschem auto-named ``net<N>`` with
    exactly one connection in the whole file, resolved through the port list
    of the subcircuit whose instance carries it.
    """
    path = os.path.join(repo_root, rel)
    with open(path, encoding="utf-8", errors="replace") as fh:
        lines = fh.readlines()

    # Every subcircuit's own port list, so an instance's node at position i
    # can be named as the port it lands on.
    ports_of = {}
    i = 0
    while i < len(lines):
        if SUBCKT_RE.match(lines[i].strip()) is None:
            i += 1
            continue
        header, i = join_continuations(lines, i)
        header_m = SUBCKT_RE.match(header.strip())
        ports_of[header_m.group(1)] = header_m.group(2).split()

    if not ports_of:
        # A device-level deck (`sim/devchar-*`, `sim/harness-selftest`) has no
        # subcircuit hierarchy at all, so it declares no port that could be
        # left dead. Nothing for this rule to grade -- counted, not passed
        # over silently, and not a parse failure either.
        hierarchyless.append(rel)
        return []

    # Instance lines are scanned across the WHOLE file, inside subcircuit
    # bodies and at the deck's top level alike: a net's connection count is
    # only meaningful if every connection in the file is counted.
    counts = {}
    sites = {}  # net -> (child subckt, port name)
    k = 0
    while k < len(lines):
        if INSTANCE_RE.match(lines[k].strip()):
            logical, k = join_continuations(lines, k)
            nodes, model = instance_nodes(logical)
            child_ports = ports_of.get(model, [])
            for idx, node in enumerate(nodes):
                if not AUTO_NET_RE.match(node):
                    continue
                counts[node] = counts.get(node, 0) + 1
                port = child_ports[idx] if idx < len(child_ports) else None
                sites[node] = (model, port)
            continue
        k += 1

    out = []
    for net, count in sorted(counts.items()):
        if count != 1:
            continue
        model, port = sites[net]
        if port is None:
            # A single-connection auto-named net on something this file does
            # not define a port list for (a primitive device, or a subcircuit
            # pulled in from elsewhere). It is still a loose end, but this
            # check cannot name the pin it landed on, so it reports it rather
            # than guessing -- naming a pad it cannot identify is how a check
            # starts fabricating findings.
            unnamed.append((rel, net, model))
            continue
        out.append((model, port, net))
    return out


def op_node_volts(log_path, node):
    """The DC operating point printed for ``node``, or None."""
    with open(log_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = OP_ROW_RE.match(line)
            if m is None or m.group(1) != node:
                continue
            try:
                return float(m.group(2))
            except ValueError:
                return None
    return None


findings = []  # (campaign, record, snapshot, child, port, net, log, volts)
snapshotless = []

for campaign_dir in sorted(glob.glob(os.path.join(repo_root, "sim", "*"))):
    if not os.path.isdir(campaign_dir):
        continue
    campaign = os.path.basename(campaign_dir)
    records = sorted(
        os.path.splitext(os.path.basename(p))[0]
        for p in glob.glob(os.path.join(campaign_dir, "records", "*.md"))
    )
    if not records:
        continue

    snaps = sorted(
        glob.glob(os.path.join(campaign_dir, "netlist-snapshots", "*.spice"))
    )
    if not snaps:
        snapshotless.append(campaign)
        continue

    for snap in snaps:
        rel = os.path.relpath(snap, repo_root)
        dead = dead_ports(rel)
        if not dead:
            continue

        stem = os.path.splitext(os.path.basename(snap))[0]
        m = RECORD_ID_RE.match(stem)
        if m is None:
            unparsed.append(
                "%s's filename does not start with a <date>-<time>-<sha> "
                "record id, so this check cannot tell which record it froze"
                % rel
            )
            continue
        record = m.group(1)

        logs = sorted(
            glob.glob(os.path.join(campaign_dir, "corners", record, "*.log"))
        )

        for child, port, net in dead:
            pad = port.lower()
            hit = None
            for log in logs:
                volts = op_node_volts(log, pad)
                if volts is not None and abs(volts) > PAD_DRIVEN_V:
                    hit = (os.path.relpath(log, repo_root), volts)
                    break
            findings.append(
                (campaign, record, rel, child, port, net, hit)
            )

for note in unparsed:
    failed = True
    sys.stderr.write("FAIL: %s\n" % note)

driven = [f for f in findings if f[6] is not None]
dormant = [f for f in findings if f[6] is None]

for campaign, record, rel, child, port, net, hit in driven:
    log, volts = hit
    dr_rel = DISCLOSED.get((campaign, record))
    if dr_rel is None:
        failed = True
        sys.stderr.write(
            "FAIL: sim/%s/records/%s.md was taken on %s, whose '.subckt %s' "
            "port %r is wired to the auto-named net %r with one connection in "
            "the whole file -- i.e. to nothing -- while that record's own log "
            "%s shows the %r pad at %.3f V. The run drove a pin its netlist "
            "could not deliver, so the configuration the design saw is not "
            "the configuration the record states it programmed. That is issue "
            "#515's defect reaching committed evidence (#557). State the "
            "effective configuration in a decision record and name it against "
            "('%s', '%s') in this check's DISCLOSED table -- do not make this "
            "check pass any other way, and do not edit the record: sim/ is "
            "append-only.\n"
            % (campaign, record, rel, child, port, net, log, port.lower(),
               volts, campaign, record)
        )
        continue

    dr_path = os.path.join(repo_root, dr_rel)
    if not os.path.isfile(dr_path):
        failed = True
        sys.stderr.write(
            "FAIL: sim/%s/records/%s.md is listed in this check's DISCLOSED "
            "table against %s, and that file does not exist. A disclosure "
            "this check cannot read is not a disclosure.\n"
            % (campaign, record, dr_rel)
        )
        continue

    size = os.path.getsize(dr_path)
    if size < DISCLOSURE_MIN_BYTES:
        failed = True
        sys.stderr.write(
            "FAIL: %s is %d bytes, under this check's %d-byte floor. A "
            "decision record short enough to be a placeholder does not state "
            "what a run actually configured.\n"
            % (dr_rel, size, DISCLOSURE_MIN_BYTES)
        )
        continue

    with open(dr_path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    if campaign not in text:
        failed = True
        sys.stderr.write(
            "FAIL: %s is named as the disclosure for sim/%s/ and never "
            "mentions %r. A disclosure that does not name the campaign it "
            "disclosed cannot be checked against it.\n"
            % (dr_rel, campaign, campaign)
        )

if failed:
    sys.exit(1)

for campaign, record, rel, child, port, net, _hit in dormant:
    print(
        "NOTE: %s leaves '.subckt %s' port %r dead (auto-named %r, one "
        "connection), and no committed log of sim/%s/corners/%s/ drives the "
        "%r pad -- nothing that record measured passed through the missing "
        "wire" % (rel, child, port, net, campaign, record, port.lower())
    )

for campaign, record, rel, child, port, net, hit in driven:
    log, volts = hit
    print(
        "DISCLOSED: sim/%s/records/%s.md drove the %r pad (%.3f V, %s) while "
        "%s leaves the '.subckt %s' port %r dead -- effective configuration "
        "stated in %s"
        % (campaign, record, port.lower(), volts, log, rel, child, port,
           DISCLOSED[(campaign, record)])
    )

for rel, net, model in unnamed:
    print(
        "NOTE: %s wires auto-named net %r to an instance of %r, which this "
        "file declares no port list for, so the pin it went dead on cannot be "
        "named -- reported rather than guessed" % (rel, net, model)
    )

if hierarchyless:
    print(
        "NOTE: %d committed snapshot(s) define no subcircuit at all "
        "(device-level decks), so they declare no port this rule could find "
        "dead -- ungradeable by this check, not graded clean"
        % len(hierarchyless)
    )

if snapshotless:
    print(
        "NOTE: %d campaign(s) with committed records have no "
        "netlist-snapshots/ directory and are therefore ungradeable by this "
        "check, not graded clean: %s"
        % (len(snapshotless), ", ".join(snapshotless))
    )

print(
    "OK: %d dead declared port(s) across the committed netlist snapshots; "
    "%d record/pin pair(s) drove one and every one of them is disclosed in a "
    "named decision record; %d did not drive it at all"
    % (len(findings), len(driven), len(dormant))
)
PY
