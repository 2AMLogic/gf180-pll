#!/usr/bin/env bash
#
# Fails if a committed design/netlist/*.spice export declares a top-level
# port that is never actually wired to anything inside its own subcircuit
# body, or carries an xschem auto-named `net<N>` net with exactly one
# connection anywhere in the file.
#
# WHY THIS EXISTS (issue #515)
#
# `design/netlist.sh --check` re-exports every schematic under design/ and
# diffs the result against the committed netlist -- it catches a STALE
# export, a netlist that no longer matches its own schematic. It cannot catch
# a schematic that is wrong in a way that still exports cleanly, because
# there is nothing for it to diff against: the export IS what the (broken)
# schematic says.
#
# That is exactly what happened. `design/pll_top.sch` placed the `LDT3` trim
# label three grid rows below the `XLD` lock-detector instance's actual
# `LDT3` pin (a coordinate mismatch between the pin's real symbol-relative
# position, above `UP`, and the label run the other three trim pins follow,
# below `DN`). The exported netlist was internally consistent with that
# mistake -- `design/netlist.sh --check` reported all seven netlists clean --
# and the defect surfaced only as a name: `XLD`'s eighth instance argument
# read `net1`, xschem's auto-generated name for a wire nobody labeled, while
# `.subckt pll_top`'s own port list still declared a real `LDT3` port two
# lines above it. The port existed; nothing inside the subcircuit touched it.
# Only 8 of the 16 lock-detector window trim codes were reachable on the
# assembled part as a result (`spec/pll.md`'s
# `Lock-detector window trim-code rule` selects code 11 for the `ff`/
# `all-fast` bundle, whose MSB is exactly the pin that had come loose).
#
# `design/lib/check-io-list-coverage.sh` (#237) checks that a `pll_top` port
# is NAMED in the Chipalooza proposal's pad table -- a documentation-coverage
# rule, not a netlist-connectivity one. It would have passed this defect
# outright: `LDT3` was a real port of `.subckt pll_top` right up until the
# fix, so it had every right to a pad-table row, and having one said nothing
# about whether the port was wired to anything past the `.subckt` line.
#
# THE TWO RULES
#
# 1. PORT CONNECTIVITY. For each committed netlist's own top-level
#    `.subckt <name> ...` block (the first one in the file, whose name
#    matches the file's own stem -- `pll_top` in `pll_top.spice`,
#    `lock_detector` in `lock_detector.spice`, and so on for every entry in
#    `design/netlist.sh`'s committed BLOCKS list), every declared port must
#    appear as a connection on some instance line inside that SAME block's
#    body. A port is looked for only at the one level of hierarchy it is
#    declared at -- exactly where `LDT3` went missing -- not by recursing
#    into the child subcircuits that block instantiates, which have their
#    own port lists checked when their own file makes them the top block.
#
# 2. THE SINGLE-CONNECTION SIGNATURE. Across the WHOLE file -- every
#    subcircuit body, not only the top one -- any node matching xschem's
#    auto-generated `net<digits>` shape must appear on at least two instance
#    connections. A net with exactly one is, by construction, wired to
#    exactly one pin: nothing else in the file ever reads or drives it. That
#    is precisely the shape `net1` had here (`XLD`'s stray `LDT3` argument,
#    with no label anywhere naming it a second time) and precisely why it is
#    a mechanically detectable condition rather than a matter of judgement --
#    a real internal signal touches at least a source and a sink. This rule
#    catches the same class of defect even when the loose end is not a
#    declared port at all (an internal auto-named node with one connection is
#    exactly as dead), and would have caught this issue's own regression on
#    its own, without rule 1 needing to know `LDT3` was a port.
#
# WHAT IT DOES NOT DO
#
# It does not simulate anything and does not know what a node is SUPPOSED to
# connect to -- only that a declared port is referenced at all (rule 1), and
# that no auto-named net is left dangling on a single pin (rule 2). A port
# wired to the WRONG pin, rather than to nothing, is invisible to both rules
# if that wrong pin happens to share a net with something else already;
# `design/lib/check-io-list-coverage.sh` and the recorded evidence in `sim/`
# are what catch a wiring mistake of that shape.
#
# Usage: design/lib/check-port-connectivity.sh [netlist.spice ...]
#   No arguments: checks every design/netlist/*.spice file.
# Exit codes: 0 every checked file's top-level ports are all referenced
#               inside their own subcircuit body, and no auto-named
#               `net<N>` in any file has fewer than two connections,
#             1 a declared port is never connected, an auto-named net has
#               exactly one connection, a graded file is missing, or the
#               file fails to parse (a broken parser must not look like a
#               clean tree).

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "FAIL: python3 is not on PATH -- this check could not run, and a" \
    "check that did not run is not a check that passed" >&2
  exit 1
fi

python3 - "${REPO_ROOT}" "$@" <<'PY'
import glob
import os
import re
import sys

repo_root = sys.argv[1]
given = sys.argv[2:]

# No arguments: every committed netlist under design/netlist/, resolved
# against REPO_ROOT rather than the caller's cwd -- so this check behaves the
# same whether it is run as `bash design/lib/check-port-connectivity.sh` from
# the repo root or exercised from a throwaway test tree.
if given:
    rel_paths = given
else:
    rel_paths = sorted(
        os.path.relpath(p, repo_root)
        for p in glob.glob(os.path.join(repo_root, "design", "netlist", "*.spice"))
    )

SUBCKT_RE = re.compile(r"^\.subckt\s+(\S+)\s*(.*)$", re.I)
ENDS_RE = re.compile(r"^\.ends\b", re.I)
INSTANCE_RE = re.compile(r"^[Xx]\S+")
AUTO_NET_RE = re.compile(r"^net\d+$")


def read(rel):
    path = os.path.join(repo_root, rel)
    if not os.path.isfile(path):
        sys.stderr.write("FAIL: %s does not exist\n" % rel)
        return None
    with open(path, encoding="utf-8") as fh:
        return fh.readlines()


def join_continuations(lines, start):
    """Join `lines[start]` with every following `+`-continuation line.

    Returns (logical_line, next_index). ngspice wraps a long `.subckt` port
    list or a long instance's parameter list onto `+` lines; a scan that
    stopped at the first newline would see a truncated line as the complete
    one.
    """
    text = lines[start].rstrip("\n")
    i = start + 1
    while i < len(lines) and lines[i].startswith("+"):
        text += " " + lines[i][1:].rstrip("\n")
        i += 1
    return text, i


def instance_nodes(logical_line):
    """The node/net tokens `logical_line` connects, in order.

    Format: `Xname node1 node2 ... nodeN modelname [param=value ...]`. The
    model/subcircuit name is the token immediately before the first
    `key=value` parameter, or the last token when there are no parameters at
    all -- either way it is not a node, and is excluded.
    """
    tokens = logical_line.split()[1:]  # drop the instance name itself
    if not tokens:
        return []
    param_idx = next((i for i, t in enumerate(tokens) if "=" in t), None)
    model_idx = (param_idx - 1) if param_idx is not None else len(tokens) - 1
    if model_idx <= 0:
        return []
    return tokens[:model_idx]


failed = False
checked = 0

for rel in rel_paths:
    lines = read(rel)
    if lines is None:
        failed = True
        continue

    stem = os.path.splitext(os.path.basename(rel))[0]

    # ---- find every `.subckt ... .ends` block, and which is the top one ----
    blocks = []  # [(name, ports, body_start, body_end)]
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        m = SUBCKT_RE.match(line)
        if m is None:
            i += 1
            continue
        header, i = join_continuations(lines, i)
        header_m = SUBCKT_RE.match(header.strip())
        name = header_m.group(1)
        ports = header_m.group(2).split()
        body_start = i
        while i < len(lines) and not ENDS_RE.match(lines[i].strip()):
            i += 1
        body_end = i  # exclusive; lines[i] is the `.ends` line (or EOF)
        blocks.append((name, ports, body_start, body_end))
        i += 1

    if not blocks:
        failed = True
        sys.stderr.write(
            "FAIL: %s has no '.subckt' block at all -- this check cannot "
            "grade a file it cannot parse\n" % rel
        )
        continue

    top = next((b for b in blocks if b[0] == stem), blocks[0])
    if top[0] != stem:
        sys.stderr.write(
            "WARN: %s's first '.subckt' is %r, not %r (the file's own "
            "name) -- checking %r's ports against its own body anyway\n"
            % (rel, top[0], stem, top[0])
        )

    # ---- rule 1: every port of the top block is connected in its own body --
    top_name, top_ports, top_start, top_end = top
    connected = set()
    j = top_start
    while j < top_end:
        line = lines[j].strip()
        if INSTANCE_RE.match(line):
            logical, j = join_continuations(lines, j)
            connected.update(instance_nodes(logical))
            continue
        j += 1

    for port in top_ports:
        if port not in connected:
            failed = True
            sys.stderr.write(
                "FAIL: %s's '.subckt %s' declares port %r, but no instance "
                "line inside that subcircuit's own body connects to it. A "
                "declared port with no connection at its own level of "
                "hierarchy is exactly issue #515's defect -- LDT3, wired to "
                "a stray auto-named net instead of the port, silently "
                "dropped 8 of 16 lock-detector trim codes\n"
                % (rel, top_name, port)
            )

    # ---- rule 2: no auto-named net<N> with exactly one connection anywhere -
    net_counts = {}
    for name, _ports, body_start, body_end in blocks:
        k = body_start
        while k < body_end:
            line = lines[k].strip()
            if INSTANCE_RE.match(line):
                logical, k = join_continuations(lines, k)
                for node in instance_nodes(logical):
                    if AUTO_NET_RE.match(node):
                        net_counts[node] = net_counts.get(node, 0) + 1
                continue
            k += 1

    for net, count in sorted(net_counts.items()):
        if count == 1:
            failed = True
            sys.stderr.write(
                "FAIL: %s has auto-named net %r with exactly 1 connection. "
                "xschem mints a 'net<N>' name for a wire nobody labeled; one "
                "with a single connection touches exactly one pin and "
                "nothing else in the file, which is the exact signature "
                "issue #515's stray LDT3 net (net1, one connection on "
                "XLD) had\n" % (rel, net)
            )

    checked += 1

if failed:
    sys.exit(1)

print(
    "OK: %d netlist(s) checked -- every top-level subcircuit's declared "
    "ports are connected inside their own body, and no auto-named 'net<N>' "
    "anywhere has fewer than 2 connections" % checked
)
PY
