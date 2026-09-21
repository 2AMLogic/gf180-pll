"""Flatten a hierarchical xschem/``design/netlist.sh`` SPICE export into one
flat ``.subckt`` (issue #440).

WHY THIS EXISTS
----------------
gf180mcu's own LVS deck (``align``) does not flatten a hierarchical
schematic netlist to match a flat GDS on its own -- it corresponds circuits
by *name*, and a flat, fully-flattened GDS top cell (the convention every
block generator in ``layout/pll_top/*`` uses -- see e.g. ``vco/block.py``'s
and ``divider_chain.py``'s own "REFERENCE NETLIST" sections) has no named
sub-circuits for the deck to match against a hierarchical reference's own
nested ``.subckt`` bodies. That failure mode was hit and documented directly
during ``divider_chain``'s own bring-up (issue #310): "a first attempt used
the generated hierarchical file directly and failed LVS outright -- every
net and device unmatched".

``vco/block.py`` and ``divider_chain.py`` each solved this the same way:
hand-composing a flat reference in Python, instance by instance, out of
each leaf/composite module's own independently-stated ``reference_netlist()``
plus an explicit net map transcribed from the schematic. That is exactly
right when a design is small enough (or built from few enough distinct
leaf cells) to transcribe by hand and cross-check by eye.

``pfd_cp`` (a nine-``.subckt``, 168-transistor hierarchy: ``pfd_cp`` ->
``pfd``/``cp`` -> ``edgedet``/``srlatch``/``cp_leg_n``/``cp_leg_p``/
``cp_dumpbuf`` -> ``pfdcp_inv_3v3``/``pfdcp_nand2_3v3``) and ``lock_detector``
(``lock_detector`` -> ``xor2_3v3``/``delaywin_3v3``/``nand2_3v3``/
``inv_3v3``/``schmitt_3v3``) are both large enough, and both already have a
schematic-derived SPICE export sitting on disk in the exact hierarchical
text this module reads (the per-record ``dut.spice`` export for ``pfd_cp``,
the committed ``design/netlist/lock_detector.spice`` for ``lock_detector``)
-- so flattening that text *mechanically* is both less error-prone than a
fresh hand transcription of 168 devices and a more literal reading of this
issue's own acceptance criteria ("a reference netlist derived from
``design/pfd_cp.sch``'s export"). This module is that mechanical flattener,
generic across both call sites (and any future one): it does not know what
a ``pfd_cp`` or a ``lock_detector`` is, only how to expand ``.subckt``
instances.

WHAT IT DOES, PRECISELY
------------------------
:func:`parse_subckts` reads every ``.subckt <name> <port>... ... .ends``
block in a SPICE text (joining ``+``-continuation lines, dropping ``*``
comments) into a :class:`Subckt`. :func:`flatten` then expands one named
top recursively: every instance line whose last non-parameter token is
itself a name in the parsed subckt table is a **subcircuit call** and is
expanded in place (its own ports rebound to the caller's actual nets, its
own internal-only nets and instance name qualified by the full instance
path so two separately-flattened instances of the same leaf cell never
collide); every other instance line is a **terminal device** (an
``nfet_03v3``/``pfet_03v3``/... primitive -- gf180mcu's LVS deck's own
``custom_classes.lvs`` recognises these model names directly, they are
never defined via a matching ``.subckt`` anywhere in this repo's exports)
and is re-emitted with its own nets renamed the same way and its own
instance name qualified with an ``M_`` prefix, the same convention
``vco/block.py``/``divider_chain.py`` already use for a flattened MOSFET
line -- but with every ``W=``/``L=``/... parameter (including the
PDK-generated ``ad=``/``as=``/``pd=``/``ps=``/``nrd=``/``nrs=``
single-quoted expressions xschem emits, which contain internal spaces and
would otherwise be torn apart by a naive ``str.split()``) carried through
byte-for-byte, not re-derived -- this module never invents or approximates
a device size.

Top-level port names are passed through unchanged (an identity port map),
so the flattened ``.subckt``'s own port list is byte-identical to the
source text's top-level ``.subckt`` line -- exactly the boundary-pin names
each caller's own layout generator already pins.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: One token, OR one ``key='...'``-with-internal-spaces token treated as a
#: single unit -- xschem's own ``ad=``/``as=``/``pd=``/``ps=``/``nrd=``/
#: ``nrs=`` parameter values are exactly this shape (e.g.
#: ``ad='int((nf+1)/2) * W/nf * 0.18u'``), and a plain ``str.split()`` would
#: otherwise fragment the quoted expression's own internal spaces into
#: several bogus tokens.
_TOKEN_RE = re.compile(r"[^\s'=]+='[^']*'|\S+")


@dataclass(frozen=True)
class Subckt:
    name: str
    ports: tuple[str, ...]
    lines: tuple[str, ...]  # one already-continuation-joined instance line each


def _tokenize(line: str) -> list[str]:
    return _TOKEN_RE.findall(line)


def _join_continuations(text: str) -> list[str]:
    """Drop ``*``-comments, join ``+``-continuation lines onto their parent."""
    joined: list[str] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("*"):
            continue
        if line.startswith("+"):
            if not joined:
                raise ValueError(f"continuation line with nothing to continue: {raw!r}")
            joined[-1] = joined[-1] + " " + line[1:].strip()
        else:
            joined.append(line)
    return joined


def parse_subckts(text: str) -> dict[str, Subckt]:
    """Every ``.subckt ... .ends`` block in ``text``, keyed by name.

    Case-insensitive on the ``.subckt``/``.ends`` keywords (xschem always
    emits lowercase, but this does not assume that); subcircuit *names* and
    net names are kept exactly as written, since gf180mcu net/model names
    are case-sensitive (``pfet_03v3`` vs a hypothetical ``PFET_03V3`` are
    not the same token to the LVS deck).
    """
    lines = _join_continuations(text)
    subckts: dict[str, Subckt] = {}
    name: str | None = None
    ports: tuple[str, ...] = ()
    body: list[str] = []
    for line in lines:
        head = line.split(None, 1)[0].lower()
        if head == ".subckt":
            if name is not None:
                raise ValueError(f".subckt {name!r} never closed with .ends")
            tokens = line.split()
            name = tokens[1]
            ports = tuple(tokens[2:])
            body = []
        elif head == ".ends":
            if name is None:
                raise ValueError(".ends with no open .subckt")
            subckts[name] = Subckt(name=name, ports=ports, lines=tuple(body))
            name = None
        elif name is not None:
            body.append(line)
        # else: a top-of-file comment/blank already dropped, or a directive
        # (e.g. a bare ``.global``) outside any .subckt -- neither call site
        # this module serves emits one; ignored rather than rejected so a
        # future export convention does not need this module's permission.
    if name is not None:
        raise ValueError(f".subckt {name!r} never closed with .ends")
    return subckts


def _split_head_params(tokens: list[str]) -> tuple[list[str], list[str]]:
    head = [t for t in tokens if "=" not in t]
    params = [t for t in tokens if "=" in t]
    return head, params


def _rename(token: str, port_map: dict[str, str], prefix: str) -> str:
    if token in port_map:
        return port_map[token]
    return f"{prefix}_{token}"


def _expand(
    subckts: dict[str, Subckt],
    lines: tuple[str, ...],
    port_map: dict[str, str],
    prefix: str,
    out: list[str],
) -> None:
    for line in lines:
        tokens = _tokenize(line)
        head, params = _split_head_params(tokens)
        inst, *nets_and_target = head
        *nets, target = nets_and_target
        if target in subckts:
            callee = subckts[target]
            if len(nets) != len(callee.ports):
                raise ValueError(
                    f"{inst}: {len(nets)} args for {target!r}'s {len(callee.ports)} ports"
                )
            child_prefix = f"{prefix}_{inst}"
            child_port_map = {
                port: _rename(arg, port_map, prefix) for port, arg in zip(callee.ports, nets)
            }
            _expand(subckts, callee.lines, child_port_map, child_prefix, out)
        else:
            new_nets = [_rename(n, port_map, prefix) for n in nets]
            new_inst = f"M_{prefix}_{inst.lstrip('xX')}"
            out.append(" ".join([new_inst, *new_nets, target, *params]))


def flatten(subckts: dict[str, Subckt], top: str) -> str:
    """Flatten ``subckts[top]`` into one flat ``.subckt <top> <ports...>``.

    Top-level ports are passed straight through under their own names (an
    identity port map): the returned text's own port list is
    byte-identical to ``subckts[top].ports``, so it names exactly the
    boundary pins the caller's own layout already pins under those names.
    """
    if top not in subckts:
        raise KeyError(f"no .subckt {top!r} in the parsed text")
    root = subckts[top]
    port_map = {p: p for p in root.ports}
    out: list[str] = []
    _expand(subckts, root.lines, port_map, top, out)
    header = f".subckt {top} {' '.join(root.ports)}"
    return "\n".join([header, *out, ".ends"]) + "\n"


def flatten_text(text: str, top: str) -> str:
    """:func:`parse_subckts` + :func:`flatten` in one call."""
    return flatten(parse_subckts(text), top)
