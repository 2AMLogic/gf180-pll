"""The loop filter's nine devices, transcribed from ``design/netlist/loop_filter.spice``.

Pure Python: no KLayout, no PDK. The values are DR-006's ratified sizing (C2's
*device* is DR-042's option-B MIM) and must not be changed here to make a layout fit -- ``layout/tests/
test_loop_filter_layout.py`` parses the committed netlist with
:func:`parse_netlist` and fails if this table and the netlist ever disagree.

Terminal order is the PDK model's own (``libs.tech/ngspice/sm141064*.ngspice``):

* ``ppolyf_u 1 2 3`` -- two resistor ends, then the substrate (``VSS``).
* ``cap_nmos_03v3_b 1 2`` -- ``1`` is the poly gate, ``2`` the n-well body.
  The model's capacitance rises with ``v(1,2)`` (``cvar3 > 0``), i.e. the gate
  accumulates the n-well under it; the LVS deck agrees
  (``moscap_extraction.lvs``: ``P1 => cap_nmos_03v3_b`` gate region,
  ``P2 => nwell_con``).
* ``cap_mim_2f0_m4m5_noshield 1 2`` (MIM option B, DR-042) and its option-A
  predecessor ``cap_mim_2f0_m2m3_noshield 1 2`` -- the LVS deck's
  ``P1 => mim_virtual`` (the bottom plate: Metal4 for B, Metal2 for A) and
  ``P2 => fuse_cap`` (the ``FuseTop`` top plate, reached through Via4 from
  Metal5 for B, Via2 from Metal3 for A). So ``VCTRL`` is the bottom plate and
  ``VSS`` the top plate in both options.

Option A is kept **only** so the committed #748 / ``pll_top`` evidence, which
was drawn and verified with it, stays reproducible (``block.build(...,
mim_option="A")``); the ratified, default device is option B.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import partial
from pathlib import Path

try:
    from .. import _canvas
except ImportError:  # this package's own dir (not its "pll_top" parent) is the
    # sys.path root under layout/tests's flat-import convention (see
    # loop_filter/primitives.py's own identical fallback).
    import _canvas

REPO_ROOT = Path(__file__).resolve().parents[3]
NETLIST = REPO_ROOT / "design" / "netlist" / "loop_filter.spice"
SUBCKT = "loop_filter"

#: Manufacturing grid (``geom.drc``'s ``ongrid(0.005)``).
LAYOUT_GRID_UM = 0.005

# Round ``v`` to the nearest manufacturing-grid point -- shared with every
# other ``layout/pll_top/*`` submodule (issue #776, ``_canvas.snap_um()``).
# ``_canvas`` imports no ``klayout`` at module level (it is lazy, inside
# ``Canvas.__post_init__``), so this module stays pure Python.
snap_um = partial(_canvas.snap_um, grid_um=LAYOUT_GRID_UM)


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


#: MIM option -> netlist model. B is the ratified C2 (DR-042); A is DR-006's
#: original device, kept for the historical evidence only (see module docstring).
MIM_MODELS: dict[str, str] = {
    "A": "cap_mim_2f0_m2m3_noshield",
    "B": "cap_mim_2f0_m4m5_noshield",
}
MIM_OPTION_OF_MODEL: dict[str, str] = {model: option for option, model in MIM_MODELS.items()}
RATIFIED_MIM_OPTION = "B"


@dataclass(frozen=True)
class MimCap:
    """One ``cap_mim_2f0_m*_noshield``: top-plate (``FuseTop``) ``w_um`` x ``l_um``."""

    name: str
    bottom_net: str  # terminal 1, the bottom plate (Metal4 for option B, Metal2 for A)
    top_net: str  # terminal 2, FuseTop top plate
    w_um: float
    l_um: float
    model: str = MIM_MODELS[RATIFIED_MIM_OPTION]

    @property
    def option(self) -> str:
        return MIM_OPTION_OF_MODEL[self.model]


#: Series chain VCTRL -> NR1 -> NR2 -> NR3 -> NZ (DR-006: "electrically one resistor").
RESISTORS: tuple[PolyRes, ...] = (
    PolyRes("XRF1", "NR1", "VCTRL", "VSS", 2.0, 107.0),
    PolyRes("XRF2", "NR2", "NR1", "VSS", 2.0, 107.0),
    PolyRes("XRF3", "NR3", "NR2", "VSS", 2.0, 107.0),
    PolyRes("XRF4", "NZ", "NR3", "VSS", 2.0, 107.0),
)

#: C1, split four ways (DR-006).
MOS_CAPS: tuple[MosCap, ...] = tuple(MosCap(f"XCF{i}", "NZ", "VSS", 87.0, 87.0) for i in range(1, 5))

def mim_caps(option: str = RATIFIED_MIM_OPTION) -> tuple[MimCap, ...]:
    """C2 as the given MIM option's device (same terminals and drawn size)."""
    return (MimCap("XCF5", "VCTRL", "VSS", 31.4, 31.4, MIM_MODELS[option]),)


#: C2 -- the ratified option-B device (DR-042).
MIM_CAPS: tuple[MimCap, ...] = mim_caps()

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
        elif inst.model in MIM_OPTION_OF_MODEL:
            bot, top = inst.nodes
            mim.append(
                MimCap(inst.name, bot, top, _um(inst.params["c_width"]), _um(inst.params["c_length"]), inst.model)
            )
        else:
            raise ValueError(f"unexpected device model {inst.model!r} ({inst.name})")
        if inst.params.get("m", "1") != "1":
            raise ValueError(f"{inst.name}: multiplier m={inst.params['m']} is not drawn by this generator")
    return tuple(res), tuple(mos), tuple(mim)


def device_area_um2(mim: tuple[MimCap, ...] = MIM_CAPS) -> float:
    """Sum of the drawn *device* areas (gate, plate, resistor body) -- not the block area."""
    return (
        sum(r.w_um * r.l_um for r in RESISTORS)
        + sum(c.w_um * c.l_um for c in MOS_CAPS)
        + sum(c.w_um * c.l_um for c in mim)
    )
