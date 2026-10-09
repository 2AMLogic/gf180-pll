"""The loop filter's nine devices, transcribed from ``design/netlist/loop_filter.spice``.

Pure Python: no KLayout, no PDK. The values are DR-006's ratified sizing and
must not be changed here to make a layout fit -- ``layout/tests/
test_loop_filter_layout.py`` parses the committed netlist with
:func:`parse_netlist` and fails if this table and the netlist ever disagree.

Terminal order is the PDK model's own (``libs.tech/ngspice/sm141064*.ngspice``):

* ``ppolyf_u 1 2 3`` -- two resistor ends, then the substrate (``VSS``).
* ``cap_nmos_03v3_b 1 2`` -- ``1`` is the poly gate, ``2`` the n-well body.
  The model's capacitance rises with ``v(1,2)`` (``cvar3 > 0``), i.e. the gate
  accumulates the n-well under it; the LVS deck agrees
  (``moscap_extraction.lvs``: ``P1 => cap_nmos_03v3_b`` gate region,
  ``P2 => nwell_con``).
* ``cap_mim_2f0_m2m3_noshield 1 2`` -- the LVS deck's ``P1 => mim_virtual``
  (the Metal2 bottom plate) and ``P2 => fuse_cap`` (the ``FuseTop`` top plate,
  reached through Via2 from Metal3). So ``VCTRL`` is the bottom plate and
  ``VSS`` the top plate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
NETLIST = REPO_ROOT / "design" / "netlist" / "loop_filter.spice"
SUBCKT = "loop_filter"

#: Manufacturing grid (``geom.drc``'s ``ongrid(0.005)``).
LAYOUT_GRID_UM = 0.005


def snap_um(v: float) -> float:
    """Round ``v`` to the nearest manufacturing-grid point."""
    return round(round(v / LAYOUT_GRID_UM) * LAYOUT_GRID_UM, 6)


@dataclass(frozen=True)
class PolyRes:
    """One plain ``ppolyf_u`` resistor: ``w_um`` across, ``l_um`` along current flow."""

    name: str
    net_a: str  # netlist terminal 1
    net_b: str  # netlist terminal 2
    sub_net: str  # netlist terminal 3 (substrate)
    w_um: float
    l_um: float
    model: str = "ppolyf_u"


@dataclass(frozen=True)
class MosCap:
    """One ``cap_nmos_03v3_b``: gate area ``w_um`` x ``l_um``."""

    name: str
    gate_net: str
    body_net: str
    w_um: float
    l_um: float
    model: str = "cap_nmos_03v3_b"


@dataclass(frozen=True)
class MimCap:
    """One ``cap_mim_2f0_m2m3_noshield``: top-plate (``FuseTop``) ``w_um`` x ``l_um``."""

    name: str
    bottom_net: str  # terminal 1, Metal2 bottom plate
    top_net: str  # terminal 2, FuseTop top plate
    w_um: float
    l_um: float
    model: str = "cap_mim_2f0_m2m3_noshield"


#: Series chain VCTRL -> NR1 -> NR2 -> NR3 -> NZ (DR-006: "electrically one resistor").
RESISTORS: tuple[PolyRes, ...] = (
    PolyRes("XRF1", "NR1", "VCTRL", "VSS", 2.0, 107.0),
    PolyRes("XRF2", "NR2", "NR1", "VSS", 2.0, 107.0),
    PolyRes("XRF3", "NR3", "NR2", "VSS", 2.0, 107.0),
    PolyRes("XRF4", "NZ", "NR3", "VSS", 2.0, 107.0),
)

#: C1, split four ways (DR-006).
MOS_CAPS: tuple[MosCap, ...] = tuple(MosCap(f"XCF{i}", "NZ", "VSS", 87.0, 87.0) for i in range(1, 5))

#: C2.
MIM_CAPS: tuple[MimCap, ...] = (MimCap("XCF5", "VCTRL", "VSS", 31.4, 31.4),)

#: The subcircuit's two ports.
PORTS: tuple[str, ...] = ("VCTRL", "VSS")

#: Every net the block carries.
NETS: tuple[str, ...] = ("VCTRL", "NR1", "NR2", "NR3", "NZ", "VSS")


@dataclass(frozen=True)
class NetlistInstance:
    name: str
    nodes: tuple[str, ...]
    model: str
    params: dict


_UNIT = {"u": 1.0, "n": 1e-3, "m": 1e3, "p": 1e-6}


def _um(value: str) -> float:
    """``"87u"`` -> 87.0 (microns)."""
    m = re.fullmatch(r"([0-9.eE+-]+)([unmp]?)", value.strip())
    if not m:
        raise ValueError(f"cannot read a length from {value!r}")
    scale = _UNIT[m.group(2)] if m.group(2) else 1e6
    return float(m.group(1)) * scale


def parse_netlist(path: Path = NETLIST, subckt: str = SUBCKT) -> tuple[tuple[str, ...], list[NetlistInstance]]:
    """Return ``(ports, instances)`` of ``subckt`` in ``path``.

    Deliberately small: the committed netlist is xschem output with one
    instance per line and no continuation lines; anything else raises rather
    than being half-read.
    """
    ports: tuple[str, ...] | None = None
    instances: list[NetlistInstance] = []
    inside = False
    for raw in Path(path).read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("*"):
            continue
        if line.startswith("+"):
            raise ValueError(f"{path}: continuation lines are not supported: {raw!r}")
        tokens = line.split()
        head = tokens[0].lower()
        if head == ".subckt" and tokens[1] == subckt:
            inside = True
            ports = tuple(tokens[2:])
            continue
        if head == ".ends" and inside:
            break
        if not inside:
            continue
        if not head.startswith("x"):
            raise ValueError(f"{path}: unexpected element {raw!r}")
        params = {}
        positional = []
        for tok in tokens[1:]:
            if "=" in tok:
                k, v = tok.split("=", 1)
                params[k] = v
            else:
                positional.append(tok)
        instances.append(NetlistInstance(tokens[0], tuple(positional[:-1]), positional[-1], params))
    if ports is None:
        raise ValueError(f"{path}: no .subckt {subckt}")
    return ports, instances


def table_from_netlist(path: Path = NETLIST) -> tuple[tuple[PolyRes, ...], tuple[MosCap, ...], tuple[MimCap, ...]]:
    """Build the device table straight from the netlist, for cross-checking :data:`RESISTORS` etc."""
    _, instances = parse_netlist(path)
    res, mos, mim = [], [], []
    for inst in instances:
        if inst.model == "ppolyf_u":
            a, b, sub = inst.nodes
            res.append(PolyRes(inst.name, a, b, sub, _um(inst.params["r_width"]), _um(inst.params["r_length"])))
        elif inst.model == "cap_nmos_03v3_b":
            g, body = inst.nodes
            mos.append(MosCap(inst.name, g, body, _um(inst.params["c_width"]), _um(inst.params["c_length"])))
        elif inst.model == "cap_mim_2f0_m2m3_noshield":
            bot, top = inst.nodes
            mim.append(MimCap(inst.name, bot, top, _um(inst.params["c_width"]), _um(inst.params["c_length"])))
        else:
            raise ValueError(f"unexpected device model {inst.model!r} ({inst.name})")
        if inst.params.get("m", "1") != "1":
            raise ValueError(f"{inst.name}: multiplier m={inst.params['m']} is not drawn by this generator")
    return tuple(res), tuple(mos), tuple(mim)


def device_area_um2() -> float:
    """Sum of the drawn *device* areas (gate, plate, resistor body) -- not the block area."""
    return (
        sum(r.w_um * r.l_um for r in RESISTORS)
        + sum(c.w_um * c.l_um for c in MOS_CAPS)
        + sum(c.w_um * c.l_um for c in MIM_CAPS)
    )
