"""``divider_chain`` -- the full block assembly (issue #310, Part 5/final of
#295's ``divider_chain`` full-custom layout decomposition).

WHAT THIS BUILDS
-----------------
The complete ``divider_chain`` block per ``design/netlist/divider_chain.spice``'s
own ``divider_chain`` subckt:

* ``XD0``..``XD5`` -- Part 4's ``div23_cell`` composite macro (issue #309),
  instantiated **six times, identically**, chained
  ``VCO -> CK1 -> CK2 -> CK3 -> CK4 -> CK5 -> CK6``.
* Termination / one-hot-mux glue logic: 5x ``nor2_3v3`` + 5x ``inv_3v3``
  forming the modulus-in feedback chain (``XNR0``-``XNR4``/``XIV0``-``XIV4``),
  6x ``nand2_3v3`` + 2x ``nand3_3v3`` + 1x ``nor2_3v3`` + 1x ``inv2x_3v3``
  forming the one-hot ``SEL0``-``SEL5`` output mux to ``DIVOUT``
  (``XM0``-``XM5``, ``XMA``, ``XMB``, ``XMNO``, ``XIDO``).
* ``XFRT`` -- one Part 3 ``dff_tg_3v3`` composite (issue #308), retiming
  ``DIVOUT`` on ``VCO`` to produce ``FB``.

452 transistors total: 360 across the six ``div23_cell`` instances (60 each)
plus 92 in the glue logic above (24 nor2_3v3 x6 + 10 inv_3v3 x5 + 24
nand2_3v3 x6 + 12 nand3_3v3 x2 + 2 inv2x_3v3 x1 + 20 dff_tg_3v3 x1).

SIX IDENTICAL ``div23_cell`` INSTANCES: GDS-LEVEL PLACEMENT, NOT SIX REDRAWS
------------------------------------------------------------------------------
Every other composite in this package (``dff_tg_3v3.py``, ``div23_cell.py``)
is flat macro composition -- every sub-cell's own devices drawn directly into
one shared ``Canvas``, no GDS-level ``CellInstArray`` hierarchy (see those
modules' own docstrings for why: composing *distinct* leaf cells into a new
macro needs a routing fabric that reasons about every net across the whole
composite, which only works if every device is a plain shape in one cell).

``div23_cell`` here is different: this block does not compose six distinct
cells, it places the *same already-built macro* six times. #295's own
acceptance criteria requires those six instances stay byte-identical -- a
future single-cell TSPC/E-TSPC swap must remain a one-symbol substitution
across all six, not something that can silently drift if one of six
independent redraws is edited without the others. So this module builds
``div23_cell`` exactly **once** (:func:`div23_cell.build`), writes it to one
scratch GDS, and places six ``klayout.db.CellInstArray`` references to that
one cell, translated into a single row -- the same technique
``layout/harness/cell.py``'s own ``build()`` already uses (the only other
``CellInstArray`` use in this repo, there placing PDK standard cells instead
of a locally-built composite). Immediately after placing all six, the top
cell is flattened (``top.flatten(-1, True)``) -- same reason
``harness/cell.py`` gives: "the DRC/LVS deck then compares a flat layout
against the flat reference netlist, with no subcircuit-correspondence
question in the way." The remaining glue logic below is drawn directly into
the same (now-flat) top cell, exactly like every other composite in this
package.

Flattening after placement does not undermine "byte-identical": the six
placements are geometrically identical copies of the one drawn cell (each
just translated by a different offset), not six independent code paths that
could drift from each other -- which is the property #295's AC actually
cares about (see that issue's own text: "a one-symbol substitution point for
a future TSPC/E-TSPC single-cell swap").

ROUTING THE SIX INSTANCES' BOUNDARY PINS: THE SAME FABRIC, ONE LEVEL UP
-------------------------------------------------------------------------
``div23_cell.py``'s own ``Div23Layout.pins`` records exactly one
representative Metal1 pad point per top-level net (``CKIN``, ``MODIN``,
``P``, ``CKOUT``, ``MODOUT``, ``VDD``, ``VSS``) -- already internally wired
throughout that macro, so a single riser landing anywhere on that pad
reaches the whole net. Translating each of the six instances' own ``pins``
dict by that instance's own placement offset gives this module the exact
physical location of every boundary connection it needs to make, without
caring at all how ``div23_cell`` wired its own interior.

Those translated points are fed into the *same* per-net Metal2/3
riser-to-bus fabric (:func:`devgen.route_net`/:class:`devgen.NetTracks`)
this package's every other composite already uses, mixed in with this
module's own freshly-drawn glue-logic pads -- one shared ``nets`` dict, one
shared :class:`devgen.NetTracks` pass, exactly like ``div23_cell.py``'s own
``build()``. The only new constraint this introduces is that the *shared*
routing base_y must sit above every div23_cell instance's own already-
flattened internal top-of-footprint (each instance's own internal Metal2/3
bus fabric is already baked into its footprint's own top edge) -- so a new,
higher-level riser continuing straight up from one of those instances' own
boundary pads never has to cross that instance's own internal geometry
sideways, only extend further up the same net's own already-reserved x
column (extending a net's own riser upward, at the same x, is the "two
risers for the same net... not a problem" case ``devgen.py``'s own "Composite
macro routing fabric" section documents).

GLUE LOGIC: THE SAME FLAT-COMPOSITE FABRIC AS ``div23_cell.py``
------------------------------------------------------------------
The termination/one-hot-mux glue (92 transistors across 46 columns: 5x
``nor2_3v3`` + 5x ``inv_3v3`` + 6x ``nand2_3v3`` + 2x ``nand3_3v3`` + 1x
``nor2_3v3`` + 1x ``inv2x_3v3`` + one ``dff_tg_3v3`` for ``XFRT``) is drawn
with exactly the same per-column, per-role (gate/channel) net-offset
bucketing and periodic-tap placement ``div23_cell.py``'s own ``build()``
already proved DRC-clean for this same leaf-cell family -- reused via this
module's own :data:`GATE_REF_DX_UM`/:data:`CHANNEL_REF_DX_UM`/etc. (imported
from that module rather than re-derived, since the underlying device
geometry -- gf180mcu's own ``nfet_03v3``/``pfet_03v3`` construction -- is
identical). Placed to the right of the six ``div23_cell`` instances, each
column tied into its own supply net (``VDD_DIV``, not ``VDD``) at its own
periodic tap pair, exactly as the block's own top-level supply domain
requires (see "VDD_DIV supply domain" below).

VDD_DIV SUPPLY DOMAIN
-----------------------
``design/netlist/divider_chain.spice``'s own subckt already names this
block's supply net ``VDD_DIV`` throughout (never ``VDD``) -- every device
here, both inside the six flattened ``div23_cell`` copies (whose own local
``VDD`` boundary pin is translated onto this block's ``VDD_DIV`` net, not
merged with any other block's supply) and in the glue logic (whose own
periodic taps are tied to ``VDD_DIV`` directly, not ``VDD``), lands on one
Metal1/2/3 fabric carrying only that name. Since this block's own generated
GDS contains no other supply net, ``VDD_DIV`` is -- by construction, not by
convention -- never physically merged with any ``VDD``/``VDD_VCO`` segment;
its own Metal2 bus (built by the shared :class:`devgen.NetTracks` pass, one
continuous run spanning every tap/pin on the net) *is* this block's own
supply trunk.

REFERENCE NETLIST: A FLATTENED RE-EXPRESSION OF THE EXISTING GENERATED ONE
------------------------------------------------------------------------------
issue #310's own Acceptance Criteria names a *specific*, already-existing
reference: ``design/netlist/divider_chain.spice``, generated by
``design/netlist.sh`` from ``design/divider_chain.sch`` and already
committed on ``main`` -- "the generated, independently-stated reference
netlist". This module's own :func:`reference_netlist` is not an independent
re-derivation of that file's content -- every device, size and connection in
it traces directly to that generated file's own ``.subckt`` bodies, via each
referenced leaf/composite module's own already-independently-stated
``reference_netlist()`` (``div23_cell.reference_netlist()``,
``nor2_3v3.reference_netlist()``, etc.) -- but it *is* a flattened
re-expression of it (:func:`_instance_body` inlines each of those, with
every net not one of that leaf's own subckt ports uniquely prefixed per
instance), not that generated file's own literal hierarchical text.

**This was not a stylistic choice; a first attempt used the generated file
directly and failed LVS with total mismatch (every net and device
unmatched).** gf180mcu's LVS deck (``align``, in
``libs.tech/klayout/lvs/gf180mcu.lvs``) does not flatten a hierarchical
schematic to match a flat layout on its own: it corresponds circuits by
*name*, and this block's own GDS (six flattened ``div23_cell``
``CellInstArray`` placements plus directly-drawn glue logic -- see "SIX
IDENTICAL ``div23_cell`` INSTANCES" above) has no named sub-circuits at all
once flattened, so there is nothing for a hierarchical reference's own
``X div23_cell`` calls to align against. Flattening the reference the same
way -- the same discipline ``div23_cell.py``/``dff_tg_3v3.py`` already use,
generalized to reuse *their* references rather than re-deriving from
scratch -- makes the comparison the same flat-vs-flat case those modules
already prove out.

NAME-BASED LVS MATCHING: WHY EVERY NET THIS MODULE ROUTES IS LABELLED
-------------------------------------------------------------------------
Flattening the reference alone was still not enough. **Confirmed
empirically**: two independent ``div23_cell`` instances, chained with no
glue logic at all, LVS-match cleanly; the same construction extended to six
chained instances (still with no glue logic) reproduces this block's own
full-design LVS mismatch, though DRC stays clean throughout. This isolates
the cause to gf180mcu's LVS comparer's own topology-only graph-matching: six
structurally identical macro copies (each already containing some internal
repetition of its own -- two ``nand2_3v3``, two ``inv_3v3``, two
``dff_tg_3v3`` instances) is enough symmetric structure that the comparer
cannot always find the correct correspondence from connectivity alone, even
though (independently confirmed by probing the reference netlist's own net
terminal lists) the connectivity itself is correct on both sides. This is a
real limitation of the comparer on a highly repetitive design, not a design
defect -- and not a `klt` (klayout-tools) gap either, since it is gf180mcu's
LVS deck driving KLayout's own native ``NetlistComparer`` directly, not
`klt`, per this repo's friction protocol (CLAUDE.md) naming `klt` gaps
specifically.

The fix: give the comparer's own name-based hint matching enough to work
with. ``div23_cell.py``'s own ``Div23Layout.pins`` only labels its 7
boundary nets, and this module previously only labelled its own 17 official
``BOUNDARY_NETS`` the same way -- leaving every glue-level/chain net this
module itself routes (``CK1``..``CK6``, ``MI0``..``MI4``, ``MO0``..``MO5``,
``T0``..``T5``, ``MA``, ``MB``, ``NMI0``..``NMI4``, ``DIVOUTB``, ``FBB``)
unlabelled and therefore anonymous to the comparer, with nothing to
distinguish, say, instance 2's own ``MI2`` from instance 3's own ``MI3``
beyond position in the overall graph. :func:`build` now labels *every* net
in its own ``nets`` dict, not just the 17 official ports -- each with the
exact same name :func:`reference_netlist` already gives it, since both are
derived from the same tables (:data:`_DIV23_NET_MAP`, :data:`_NOR_SPECS`,
etc.). That anchors every one of the six ``div23_cell`` instances' own
boundary uniquely by name, which is sufficient: each instance's own
*internal-only* nets (``SB``, ``DQN``, ``Q``, ``QB``, ``NMO``, ``DMO``,
``MOB``, and each of its two ``dff_tg_3v3``'s own six internal nets) stay
unlabelled -- exactly as they were in ``div23_cell.py``'s own standalone,
independently-LVS-clean build -- because once an instance's own boundary is
correctly anchored, resolving its own 60-device interior is the same
bounded, already-proven-tractable problem that build already solves on its
own, not a new one this module reopens.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from . import devgen, dff_tg_3v3, div23_cell, inv2x_3v3, inv_3v3, nand2_3v3, nand3_3v3, nor2_3v3
from .devgen import Canvas, NetTracks, offset_pad_x, pad_center, route_net, well_tap

TOP_CELL = "divider_chain"

#: This block's own top-level I/O (``design/divider_chain.sch``'s subckt
#: ports), per ``design/netlist/divider_chain.spice``'s own
#: ``.subckt divider_chain VCO P0 .. P5 SEL0 .. SEL5 DIVOUT FB VDD_DIV VSS``
#: header.
BOUNDARY_NETS: tuple[str, ...] = (
    "VCO",
    "P0", "P1", "P2", "P3", "P4", "P5",
    "SEL0", "SEL1", "SEL2", "SEL3", "SEL4", "SEL5",
    "DIVOUT", "FB",
    "VDD_DIV", "VSS",
)

#: Per-instance global net mapping for the six ``div23_cell`` copies
#: (``XD0``..``XD5``), read straight off
#: ``design/netlist/divider_chain.spice``'s own X-instance list:
#:
#:     XD0 VCO MI0 P0 CK1 MO0 VDD_DIV VSS div23_cell
#:     XD1 CK1 MI1 P1 CK2 MO1 VDD_DIV VSS div23_cell
#:     XD2 CK2 MI2 P2 CK3 MO2 VDD_DIV VSS div23_cell
#:     XD3 CK3 MI3 P3 CK4 MO3 VDD_DIV VSS div23_cell
#:     XD4 CK4 MI4 P4 CK5 MO4 VDD_DIV VSS div23_cell
#:     XD5 CK5 SEL5 P5 CK6 MO5 VDD_DIV VSS div23_cell
#:
#: ``VDD``/``VSS`` are handled uniformly for every instance (see
#: :func:`build`), not repeated in this table.
_DIV23_NET_MAP: tuple[dict[str, str], ...] = (
    {"CKIN": "VCO", "MODIN": "MI0", "P": "P0", "CKOUT": "CK1", "MODOUT": "MO0"},
    {"CKIN": "CK1", "MODIN": "MI1", "P": "P1", "CKOUT": "CK2", "MODOUT": "MO1"},
    {"CKIN": "CK2", "MODIN": "MI2", "P": "P2", "CKOUT": "CK3", "MODOUT": "MO2"},
    {"CKIN": "CK3", "MODIN": "MI3", "P": "P3", "CKOUT": "CK4", "MODOUT": "MO3"},
    {"CKIN": "CK4", "MODIN": "MI4", "P": "P4", "CKOUT": "CK5", "MODOUT": "MO4"},
    {"CKIN": "CK5", "MODIN": "SEL5", "P": "P5", "CKOUT": "CK6", "MODOUT": "MO5"},
)

#: Horizontal clearance between two adjacent ``div23_cell`` instances' own
#: drawn extents -- generous headroom past NW.2b's ~1.4 um min nwell-to-nwell
#: spacing (see ``vco/block.py``'s own citation of the same rule), since each
#: instance's own nwell already reaches close to its footprint's own edge.
DIV23_GAP_X_UM = 20.0

#: Horizontal clearance between the sixth ``div23_cell`` instance's own
#: drawn extent and the first glue-logic column -- same rationale/value as
#: :data:`DIV23_GAP_X_UM`.
GLUE_GAP_X_UM = 20.0

#: Reused unchanged from ``div23_cell.py`` -- the same leaf-cell family, same
#: proven-DRC-clean net-offset/tap geometry (see that module's own
#: docstring's "NET-COLLISION FIX" section for the full derivation).
NET_OFFSET_STEP_UM = div23_cell.NET_OFFSET_STEP_UM
GATE_REF_DX_UM = div23_cell.GATE_REF_DX_UM
CHANNEL_REF_DX_UM = div23_cell.CHANNEL_REF_DX_UM
TAP_LEFT_MARGIN_UM = div23_cell.TAP_LEFT_MARGIN_UM
TAP_OFFSET_UM = div23_cell.TAP_OFFSET_UM
PTAP_Y0_UM = div23_cell.PTAP_Y0_UM
NTAP_Y0_UM = div23_cell.NTAP_Y0_UM
COLUMN_CLEAR_GAP_UM = div23_cell.COLUMN_CLEAR_GAP_UM

#: Reused private helpers from ``div23_cell.py`` -- same package, same
#: leaf-cell family, deliberately not duplicated (unlike the *constants*
#: above, which this module also could have re-derived, these are enough
#: logic that duplicating them would be a real drift risk for no benefit).
_leaf_columns = div23_cell._leaf_columns
_split_branches = div23_cell._split_branches
_dff_columns = div23_cell._dff_columns
_draw_branch = div23_cell._draw_branch

_Placement = tuple[devgen.Column, dict[str, str]]

#: XNR0..XNR4 / XIV0..XIV4 -- modulus-in feedback chain. Shared between
#: :func:`_glue_placements` (physical layout) and :func:`reference_netlist`
#: (flattened LVS reference generation) so the two can never drift apart.
_NOR_SPECS: tuple[tuple[str, str, str, str], ...] = (
    ("XNR0", "MO1", "SEL0", "NMI0"),
    ("XNR1", "MO2", "SEL1", "NMI1"),
    ("XNR2", "MO3", "SEL2", "NMI2"),
    ("XNR3", "MO4", "SEL3", "NMI3"),
    ("XNR4", "MO5", "SEL4", "NMI4"),
)
_INV_SPECS: tuple[tuple[str, str, str], ...] = (
    ("XIV0", "NMI0", "MI0"),
    ("XIV1", "NMI1", "MI1"),
    ("XIV2", "NMI2", "MI2"),
    ("XIV3", "NMI3", "MI3"),
    ("XIV4", "NMI4", "MI4"),
)
#: XM0..XM5 -- one-hot AND-gate first stage.
_NAND2_SPECS: tuple[tuple[str, str, str, str], ...] = (
    ("XM0", "CK1", "SEL0", "T0"),
    ("XM1", "CK2", "SEL1", "T1"),
    ("XM2", "CK3", "SEL2", "T2"),
    ("XM3", "CK4", "SEL3", "T3"),
    ("XM4", "CK5", "SEL4", "T4"),
    ("XM5", "CK6", "SEL5", "T5"),
)


def _glue_placements() -> list[_Placement]:
    """The 46 columns (92 transistors) of termination/one-hot-mux glue logic,
    in ``design/netlist/divider_chain.spice``'s own X-instance order -- see
    module docstring's "GLUE LOGIC" section.
    """
    result: list[_Placement] = []

    for (nname, a, b, y), (_iname, ia, iy) in zip(_NOR_SPECS, _INV_SPECS):
        result += _leaf_columns(
            nor2_3v3.COLUMNS, {"A": a, "B": b, "Y": y, "VDD": "VDD_DIV", "VSS": "VSS", "PMID": f"{nname}_PMID"}
        )
        result.append((_split_branches(inv_3v3.INV_DEVICES), {"A": ia, "Y": iy, "VDD": "VDD_DIV", "VSS": "VSS"}))

    for name, a, b, y in _NAND2_SPECS:
        result += _leaf_columns(
            nand2_3v3.COLUMNS, {"A": a, "B": b, "Y": y, "VDD": "VDD_DIV", "VSS": "VSS", "NMID": f"{name}_NMID"}
        )

    # XMA/XMB -- one-hot AND-gate second stage (3-input).
    result += _leaf_columns(
        nand3_3v3.COLUMNS,
        {"A": "T0", "B": "T1", "C": "T2", "Y": "MA", "VDD": "VDD_DIV", "VSS": "VSS", "NM1": "XMA_NM1", "NM2": "XMA_NM2"},
    )
    result += _leaf_columns(
        nand3_3v3.COLUMNS,
        {"A": "T3", "B": "T4", "C": "T5", "Y": "MB", "VDD": "VDD_DIV", "VSS": "VSS", "NM1": "XMB_NM1", "NM2": "XMB_NM2"},
    )

    # XMNO/XIDO -- one-hot mux output stage.
    result += _leaf_columns(
        nor2_3v3.COLUMNS, {"A": "MA", "B": "MB", "Y": "DIVOUTB", "VDD": "VDD_DIV", "VSS": "VSS", "PMID": "XMNO_PMID"}
    )
    result += _leaf_columns(inv2x_3v3.COLUMNS, {"A": "DIVOUTB", "Y": "DIVOUT", "VDD": "VDD_DIV", "VSS": "VSS"})

    # XFRT -- divider-retiming flop (Part 3's dff_tg_3v3, issue #308).
    result += _dff_columns(
        "XFRT", {"D": "DIVOUT", "CK": "VCO", "Q": "FB", "QB": "FBB", "VDD": "VDD_DIV", "VSS": "VSS"}
    )

    return result


def _rename_token(token: str, prefix: str, port_map: dict[str, str]) -> str:
    """One SPICE-line token, renamed for one flattened instance -- see
    :func:`_instance_body`'s own docstring.
    """
    if token in port_map:
        return port_map[token]
    if "_03v3" in token or "=" in token:
        return token  # PDK model name (pfet_03v3/nfet_03v3) or a W=/L=/... parameter
    return f"{prefix}_{token}"


def _rename_line(line: str, prefix: str, port_map: dict[str, str]) -> str:
    tokens = line.split()
    device_name, *rest = tokens
    renamed_device = f"M_{prefix}_{device_name[2:]}" if device_name.startswith("M_") else device_name
    return " ".join([renamed_device] + [_rename_token(t, prefix, port_map) for t in rest])


def _instance_body(ref_text: str, prefix: str, port_map: dict[str, str]) -> str:
    """Flatten one standalone leaf/composite module's own
    ``reference_netlist()`` text into ``prefix``-qualified ``M`` lines, for
    reuse inside this block's own flattened reference netlist -- see module
    docstring's "REFERENCE NETLIST" section for why this block's own
    reference is the pre-existing ``design/netlist/divider_chain.spice``, not
    a fresh hand-written one, and why that reference still needs to be a
    *flat* ``M``-line list here rather than reusable as literal text: gf180mcu's
    LVS deck (``align``) does not flatten a hierarchical schematic to match a
    flat layout on its own (confirmed empirically: comparing this block's
    flat GDS directly against the hierarchical
    ``design/netlist/divider_chain.spice`` produced total mismatch -- every
    net and device unmatched -- because the deck's ``align`` step only
    corresponds circuits by name, and this block's GDS has none once
    flattened). Flattening this reference the same way keeps the *content*
    independently derived from ``design/netlist/divider_chain.spice`` (every
    device/size/connection below is that generated file's own, only
    re-expressed flat) while making the comparison the same flat-vs-flat
    case ``div23_cell.py``/``dff_tg_3v3.py`` already prove out.

    Every net named in ``port_map`` (that leaf/composite's own subckt ports,
    including ``VDD``/``VSS``) is translated to this block's own global net
    name; every other token that is not a PDK model name or a ``KEY=value``
    parameter is a net local to that one standalone reference (e.g.
    ``nor2_3v3``'s own internal ``PMID``) and gets ``prefix_``-qualified so
    multiple instances of the same leaf cell stay electrically distinct once
    flattened together. Device names (``M_...``) are always ``prefix_``-
    qualified, for the same reason.
    """
    lines = [line for line in ref_text.splitlines() if line.startswith("M_")]
    return "\n".join(_rename_line(line, prefix, port_map) for line in lines) + "\n"


def reference_netlist() -> str:
    """This block's own flattened LVS reference netlist -- see
    :func:`_instance_body`'s docstring for why this is a flattened
    re-expression of ``design/netlist/divider_chain.spice`` (the real
    Acceptance-Criteria reference) rather than an independently hand-derived
    netlist: every device/connection below traces directly to that
    generated file's own ``.subckt`` bodies (``div23_cell``, ``nor2_3v3``,
    ``inv_3v3``, ``nand2_3v3``, ``nand3_3v3``, ``inv2x_3v3``,
    ``dff_tg_3v3``), each already independently stated by its own module's
    ``reference_netlist()`` (which this function reuses, unmodified, as the
    per-instance source text) -- not re-derived here.
    """
    body = ""

    for i in range(6):
        net_map = _DIV23_NET_MAP[i]
        port_map = {
            "CKIN": net_map["CKIN"],
            "MODIN": net_map["MODIN"],
            "P": net_map["P"],
            "CKOUT": net_map["CKOUT"],
            "MODOUT": net_map["MODOUT"],
            "VDD": "VDD_DIV",
            "VSS": "VSS",
        }
        body += _instance_body(div23_cell.reference_netlist(), f"XD{i}", port_map)

    for (nname, a, b, y), (_iname, ia, iy) in zip(_NOR_SPECS, _INV_SPECS):
        body += _instance_body(
            nor2_3v3.reference_netlist(), nname, {"A": a, "B": b, "Y": y, "VDD": "VDD_DIV", "VSS": "VSS"}
        )
        body += _instance_body(
            inv_3v3.reference_netlist(), _iname, {"A": ia, "Y": iy, "VDD": "VDD_DIV", "VSS": "VSS"}
        )

    for name, a, b, y in _NAND2_SPECS:
        body += _instance_body(
            nand2_3v3.reference_netlist(), name, {"A": a, "B": b, "Y": y, "VDD": "VDD_DIV", "VSS": "VSS"}
        )

    body += _instance_body(
        nand3_3v3.reference_netlist(),
        "XMA",
        {"A": "T0", "B": "T1", "C": "T2", "Y": "MA", "VDD": "VDD_DIV", "VSS": "VSS"},
    )
    body += _instance_body(
        nand3_3v3.reference_netlist(),
        "XMB",
        {"A": "T3", "B": "T4", "C": "T5", "Y": "MB", "VDD": "VDD_DIV", "VSS": "VSS"},
    )
    body += _instance_body(
        nor2_3v3.reference_netlist(),
        "XMNO",
        {"A": "MA", "B": "MB", "Y": "DIVOUTB", "VDD": "VDD_DIV", "VSS": "VSS"},
    )
    body += _instance_body(
        inv2x_3v3.reference_netlist(),
        "XIDO",
        {"A": "DIVOUTB", "Y": "DIVOUT", "VDD": "VDD_DIV", "VSS": "VSS"},
    )
    body += _instance_body(
        dff_tg_3v3.reference_netlist(),
        "XFRT",
        {"D": "DIVOUT", "CK": "VCO", "Q": "FB", "QB": "FBB", "VDD": "VDD_DIV", "VSS": "VSS"},
    )

    ports = " ".join(BOUNDARY_NETS)
    return (
        "* Reference schematic for divider_chain (issue #310).\n"
        "*\n"
        "* Flattened re-expression of design/netlist/divider_chain.spice (the\n"
        "* Acceptance-Criteria reference netlist, generated by design/netlist.sh\n"
        "* from design/divider_chain.sch) -- see divider_chain.py's own\n"
        "* _instance_body() docstring for why a flat re-expression rather than\n"
        "* that file's own hierarchical text: gf180mcu's LVS deck does not\n"
        "* flatten a hierarchical schematic to match this block's flat GDS on\n"
        "* its own. Every device/connection below traces to that generated\n"
        "* file's own subckt bodies (div23_cell, nor2_3v3, inv_3v3, nand2_3v3,\n"
        "* nand3_3v3, inv2x_3v3, dff_tg_3v3), via each of those modules' own\n"
        "* independently-stated reference_netlist().\n"
        "*\n"
        "* Run LVS with --lvs_sub=VSS (layout/run_pv.py's own default): the NMOS\n"
        "* body ties to the deck's synthesized global substrate net, which this\n"
        "* flag names VSS -- see layout/README.md's \"substrate-net gotcha\".\n"
        "\n"
        f".subckt {TOP_CELL} {ports}\n"
        f"{body}"
        ".ends\n"
    )


@dataclass
class DividerChainLayout:
    canvas: Canvas
    footprint: tuple[float, float, float, float]
    pins: dict[str, tuple[float, float]] = field(default_factory=dict)

    def write_gds(self, path) -> None:
        self.canvas.write_gds(path)


def build(outdir: Path | None = None) -> DividerChainLayout:
    import klayout.db as db  # noqa: PLC0415 -- lazy, same convention as every module in this package

    # --- six identical div23_cell instances, GDS-level placement -- see
    # module docstring's "SIX IDENTICAL div23_cell INSTANCES" section. ---
    div23 = div23_cell.build()
    div23_w = div23.footprint[2] - div23.footprint[0]
    base_dx = -div23.footprint[0]
    base_dy = -div23.footprint[1]

    canvas = Canvas(TOP_CELL)

    with tempfile.TemporaryDirectory() as tmp:
        div23_gds = Path(tmp) / "div23_cell.gds"
        div23.write_gds(div23_gds)
        canvas.layout.read(str(div23_gds))
    div23_index = canvas.layout.cell_by_name("div23_cell")

    dbu_per_um = int(round(1.0 / canvas.dbu))
    offsets: list[tuple[float, float]] = []
    for i in range(6):
        dx = base_dx + i * (div23_w + DIV23_GAP_X_UM)
        dy = base_dy
        offsets.append((dx, dy))
        trans = db.Trans(db.Vector(int(round(dx * dbu_per_um)), int(round(dy * dbu_per_um))))
        canvas.top.insert(db.CellInstArray(div23_index, trans))

    # Flatten immediately -- see module docstring for why (harness/cell.py's
    # own precedent: a flat top cell needs no subcircuit correspondence with
    # the (hierarchical) reference netlist during LVS).
    canvas.top.flatten(-1, True)

    nets: dict[str, list[tuple[float, float]]] = {}

    def _add(net: str, point: tuple[float, float]) -> None:
        nets.setdefault(net, []).append(point)

    for i, (dx, dy) in enumerate(offsets):
        net_map = _DIV23_NET_MAP[i]
        for local, (px, py) in div23.pins.items():
            if local == "VDD":
                global_net = "VDD_DIV"
            elif local == "VSS":
                global_net = "VSS"
            else:
                global_net = net_map[local]
            _add(global_net, (px + dx, py + dy))

    # --- glue logic: same flat-composite fabric as div23_cell.py's own
    # build() -- see module docstring's "GLUE LOGIC" section. ---
    pfet_boxes: list[tuple[float, float, float, float]] = []
    x_cursor = offsets[-1][0] + div23_w + GLUE_GAP_X_UM

    for col, port_map in _glue_placements():
        devices = col.pulldown + col.pullup
        pd_ports = _draw_branch(canvas, col.pulldown, x_cursor, devgen.ROW_PD_Y0)
        pu_ports = _draw_branch(canvas, col.pullup, x_cursor, devgen.ROW_PU_Y0)
        ports = pd_ports + pu_ports

        for p in ports:
            if p.kind == "pfet":
                pfet_boxes.append((p.x0, p.y0, p.x1, p.y3))

        roles: dict[str, list[tuple[str, tuple[float, float, float, float]]]] = {"gate": [], "channel": []}
        for d, p in zip(devices, ports):
            roles["gate"].append((port_map[d.gate_net], p.gate_pad))
            roles["channel"].append((port_map[d.top_net], p.top_pad))
            roles["channel"].append((port_map[d.bottom_net], p.bottom_pad))
        role_reference = {"gate": x_cursor + GATE_REF_DX_UM, "channel": x_cursor + CHANNEL_REF_DX_UM}
        channel_max_reach = x_cursor
        for role, items in roles.items():
            if not items:
                continue
            reference_x = role_reference[role]
            nets_here = sorted({n for n, _ in items})
            n = len(nets_here)
            role_offsets = {net: (idx - (n - 1) / 2.0) * NET_OFFSET_STEP_UM for idx, net in enumerate(nets_here)}
            if role == "channel":
                channel_max_reach = reference_x + max(role_offsets.values())
            for net, pad in items:
                target_dx = reference_x + role_offsets[net] - pad_center(pad)[0]
                point = pad_center(pad) if target_dx == 0.0 else offset_pad_x(canvas, pad, target_dx)
                _add(net, point)

        col_right = max([p.x1 for p in ports] + [channel_max_reach], default=x_cursor)
        half_tap = devgen.TAP_SIZE_UM / 2.0
        gx = col_right + TAP_LEFT_MARGIN_UM
        ntap_pad = well_tap(canvas, "n", gx - half_tap, NTAP_Y0_UM, "VDD_DIV")
        _add("VDD_DIV", pad_center(ntap_pad))
        pfet_boxes.append((gx - half_tap, NTAP_Y0_UM, gx + half_tap, NTAP_Y0_UM + devgen.TAP_SIZE_UM))
        ptap_pad = well_tap(canvas, "p", gx - half_tap, PTAP_Y0_UM, "VSS")
        _add("VSS", offset_pad_x(canvas, ptap_pad, TAP_OFFSET_UM))

        x_cursor = col_right + COLUMN_CLEAR_GAP_UM

    glue_nwell_box = devgen.nwell_over(canvas, pfet_boxes)

    # --- unify: one shared NetTracks pass, based above every div23_cell
    # instance's own already-flattened top edge and the glue logic's own
    # nwell top -- see module docstring's "ROUTING THE SIX INSTANCES' BOUNDARY
    # PINS" section for why this is safe. ---
    max_div23_top = max(dy + div23.footprint[3] for _dx, dy in offsets)
    base_y = max(max_div23_top, glue_nwell_box[3]) + 3.0
    tracks = NetTracks(base_y=base_y)
    for net, pads in nets.items():
        route_net(canvas, net, pads, tracks.get(net))

    # Label every net this module itself routes -- not just this block's own
    # 17 official BOUNDARY_NETS -- with its own reference-netlist name. See
    # module docstring's "NAME-BASED LVS MATCHING" section: gf180mcu's LVS
    # comparer cannot disambiguate this design's six structurally-identical
    # div23_cell copies from topology alone (confirmed empirically -- see
    # that section), so every one of this module's own glue-level/chain nets
    # (``CK1``..``CK6``, ``MI0``..``MI4``, ``MO0``..``MO5``, etc., not only
    # this block's external ports) needs its own distinguishing label for the
    # comparer's name-based hint matching to seed a correct match. Only
    # ``div23_cell``'s own *internal-only* nets (its own ``SB``/``DQN``/``Q``/
    # etc., never surfaced to this module's own ``nets`` dict at all) are not
    # covered this way -- see that same docstring section for why that is
    # still sufficient.
    pins: dict[str, tuple[float, float]] = {}
    for net, points in nets.items():
        x, y = points[0]
        canvas.label("metal1_label", net, x, y)
        if net in BOUNDARY_NETS:
            pins[net] = (x, y)

    drawn = canvas.top.bbox()
    dbu = canvas.dbu
    footprint = (
        round(drawn.left * dbu, 6),
        round(drawn.bottom * dbu, 6),
        round(drawn.right * dbu, 6),
        round(drawn.top * dbu, 6),
    )

    layout = DividerChainLayout(canvas=canvas, footprint=footprint, pins=pins)
    if outdir is not None:
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        layout.write_gds(outdir / f"{TOP_CELL}.gds")
    return layout


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    default_outdir = Path(__file__).resolve().parents[2] / "evidence" / "divider-chain-layout" / "work"
    parser.add_argument("--outdir", default=str(default_outdir))
    args = parser.parse_args()
    outdir = Path(args.outdir)
    layout = build(outdir)
    netlist_path = outdir / f"{TOP_CELL}.spice"
    netlist_path.write_text(reference_netlist())
    x0, y0, x1, y1 = layout.footprint
    print(f"wrote {outdir}/{TOP_CELL}.gds")
    print(f"wrote {netlist_path}")
    print("instances : 6 div23_cell + 20 glue-logic gates + 1 dff_tg_3v3 (XFRT)")
    print("devices   : 452 (360 across the six div23_cell instances + 92 glue logic)")
    print(f"footprint : {x1 - x0:.3f} x {y1 - y0:.3f} um  ({(x1 - x0) * (y1 - y0):.1f} um^2)")
    print(f"pins      : {sorted(layout.pins)}")
    for net in BOUNDARY_NETS:
        print(f"  {net:8s} @ {layout.pins[net]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
