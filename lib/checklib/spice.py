"""SPICE netlist text helpers shared by the connectivity checkers.

``join_continuations`` and ``instance_nodes`` parse ngspice deck text: the
wrapped-line and instance-line shapes ``sim/lib/check-record-trim-
connectivity.sh`` and ``design/lib/check-port-connectivity.sh`` both grade.
Both were pasted into each heredoc and had begun to drift in their
docstrings; the bodies live here once.
"""


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
    """The node/net tokens `logical_line` connects, in order, and its model.

    Format: `Xname node1 node2 ... nodeN modelname [param=value ...]`. The
    model/subcircuit name is the token immediately before the first
    `key=value` parameter, or the last token when there are no parameters at
    all -- either way it is not a node, and is excluded.

    Returns (nodes, model); a caller that does not need the model name
    discards it.
    """
    tokens = logical_line.split()[1:]  # drop the instance name itself
    if not tokens:
        return [], None
    param_idx = next((i for i, t in enumerate(tokens) if "=" in t), None)
    model_idx = (param_idx - 1) if param_idx is not None else len(tokens) - 1
    if model_idx <= 0:
        return [], None
    return tokens[:model_idx], tokens[model_idx]
