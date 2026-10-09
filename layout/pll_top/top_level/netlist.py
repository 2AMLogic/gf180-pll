"""The ``pll_top`` instance list, read from ``design/netlist/pll_top.spice``.

Every top-level connection this package draws comes from here: which block
port sits on which top-level net. Reading the committed netlist rather than
restating it means a schematic change that renames or rewires a port breaks
the assembly instead of silently leaving the layout behind.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
NETLIST = REPO_ROOT / "design" / "netlist" / "pll_top.spice"
TOP_SUBCKT = "pll_top"


@dataclass(frozen=True)
class Instance:
    name: str  # e.g. "XPFD"
    subckt: str  # e.g. "pfd_cp"
    nets: tuple[str, ...]  # top-level nets, in port order
    ports: tuple[str, ...]  # the subcircuit's own port names, same order

    def port_net(self) -> dict[str, str]:
        return dict(zip(self.ports, self.nets))


@dataclass(frozen=True)
class TopNetlist:
    pins: tuple[str, ...]
    instances: tuple[Instance, ...]

    def instance(self, subckt: str) -> Instance:
        for inst in self.instances:
            if inst.subckt == subckt:
                return inst
        raise KeyError(subckt)

    def terminals(self) -> dict[str, list[tuple[str, str]]]:
        """``{top net: [(subckt, port), ...]}`` for every net that touches a block."""
        out: dict[str, list[tuple[str, str]]] = {}
        for inst in self.instances:
            for port, net in inst.port_net().items():
                out.setdefault(net, []).append((inst.subckt, port))
        return out


def _logical_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.startswith("*"):
            continue
        if line.startswith("+") and lines:
            lines[-1] += " " + line[1:].strip()
        else:
            lines.append(line.strip())
    return lines


def read(path: Path = NETLIST) -> TopNetlist:
    lines = _logical_lines(Path(path).read_text(encoding="utf-8"))
    ports: dict[str, tuple[str, ...]] = {}
    bodies: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines:
        tok = line.split()
        if tok[0].lower() == ".subckt":
            current = tok[1]
            ports[current] = tuple(tok[2:])
            bodies[current] = []
        elif tok[0].lower() == ".ends":
            current = None
        elif current is not None:
            bodies[current].append(line)
    if TOP_SUBCKT not in ports:
        raise ValueError(f"{path}: no .subckt {TOP_SUBCKT}")
    instances = []
    for line in bodies[TOP_SUBCKT]:
        tok = line.split()
        if not tok[0].upper().startswith("X"):
            raise ValueError(f"{path}: unexpected top-level element {tok[0]!r}")
        params = [t for t in tok[1:] if "=" in t]
        if params:
            raise ValueError(f"{path}: top-level instance {tok[0]} carries parameters {params}")
        subckt = tok[-1]
        nets = tuple(tok[1:-1])
        if subckt not in ports:
            raise ValueError(f"{path}: {tok[0]} instantiates undefined subckt {subckt}")
        if len(nets) != len(ports[subckt]):
            raise ValueError(f"{path}: {tok[0]} has {len(nets)} nets, {subckt} has {len(ports[subckt])} ports")
        instances.append(Instance(tok[0], subckt, nets, ports[subckt]))
    return TopNetlist(pins=ports[TOP_SUBCKT], instances=tuple(instances))
