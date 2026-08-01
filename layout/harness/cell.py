"""The trivial cell that proves the DRC/LVS flow.

WHAT IT IS
----------
``inv_tb`` -- a single flattened top cell containing one gf180mcu 9-track
standard-cell inverter (``gf180mcu_fd_sc_mcu9t5v0__clkinv_1``) with the well
and substrate taps it needs to stand alone:

    endcap | filltie | clkinv_1 | filltie | endcap
      0.0     1.12      2.24       4.48      5.60    (um, abutted, 5.04 um row)

WHY THE TAPS ARE NOT OPTIONAL
-----------------------------
An inverter cell *by itself* is not DRC clean, and that is not a tool
problem. Rules DF.13_MV / DF.14_MV cap the distance from any NCOMP-in-nwell
to an nwell tap, and from any PCOMP-outside-nwell to a substrate tap, at
15 um. A standard cell carries no taps -- in a real row they come from the
tie/fill cells -- so the bare cell violates both rules the moment it is
streamed out on its own. This was observed, not assumed: see the
``bare-cell`` control in ``layout/evidence/``, which records the bare
``clkinv_1`` failing exactly those two rules.

Building the proof vehicle from the installed PDK (rather than vendoring a
GDS into this repo) keeps the artifact reproducible from whatever gf180mcu
install ``sim/harness/pdk.py`` resolves, and keeps foundry geometry out of
this repository.

The matching LVS reference netlist is written alongside it. It is
deliberately hand-written rather than lifted from the PDK's CDL: the point of
an LVS proof is that an *independently stated* schematic matches the layout.
The device sizes are the ones the cell's own ``.cdl`` documents (nfet_05v0
W=0.73/L=0.6, pfet_05v0 W=1.83/L=0.5).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

STDCELL_PREFIX = "gf180mcu_fd_sc_mcu9t5v0__"
TOP_CELL = "inv_tb"

#: (cell suffix, LEF width in um, mirror-in-x?) -- abutted left to right.
#: Widths are the LEF ``SIZE`` values; the right-hand endcap is mirrored so
#: its well/implant overhang points outward, as it would at the end of a row.
ROW = (
    ("endcap", 1.12, False),
    ("filltie", 1.12, False),
    ("clkinv_1", 2.24, False),
    ("filltie", 1.12, False),
    ("endcap", 1.12, True),
)

REFERENCE_NETLIST = """\
* Reference schematic for the layout/ DRC+LVS flow proof (issue #16).
*
* Hand-written on purpose: LVS is only evidence if the schematic is stated
* independently of the layout. Device sizes are the ones the gf180mcu
* standard-cell CDL documents for gf180mcu_fd_sc_mcu9t5v0__clkinv_1.
*
* Bulk terminals are tied to the rails because the filltie cells in the row
* tie nwell -> VDD and p-substrate -> VSS. Run LVS with --lvs_sub=VSS so the
* extractor names the global substrate net VSS to match (see layout/README.md
* -> "The substrate-net gotcha").

.subckt inv_tb I ZN VDD VSS
M_i_0 ZN I VSS VSS nfet_05v0 W=0.73u L=0.6u
M_i_1 ZN I VDD VDD pfet_05v0 W=1.83u L=0.5u
.ends
"""


@dataclass(frozen=True)
class TrivialCell:
    gds: Path
    netlist: Path
    topcell: str = TOP_CELL


def build(outdir: Path, stdcell_gds: Path) -> TrivialCell:
    """Assemble ``inv_tb.gds`` + ``inv_tb.spice`` under ``outdir``."""
    import klayout.db as db  # imported lazily: the CLI's --help must not need it

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    layout = db.Layout()
    layout.read(str(stdcell_gds))
    dbu_per_um = int(round(1.0 / layout.dbu))

    top = layout.create_cell(TOP_CELL)
    x_um = 0.0
    for suffix, width_um, mirror in ROW:
        index = layout.cell_by_name(STDCELL_PREFIX + suffix)
        if mirror:
            # Mirror about the y axis, then shift right so the mirrored cell
            # occupies [x, x+width] again.
            trans = db.Trans(2, True, int(round((x_um + width_um) * dbu_per_um)), 0)
        else:
            trans = db.Trans(db.Vector(int(round(x_um * dbu_per_um)), 0))
        top.insert(db.CellInstArray(index, trans))
        x_um += width_um

    # Flatten so the streamed-out cell is a single self-contained top cell:
    # the LVS deck then compares a flat layout against the flat reference
    # netlist, with no subcircuit-correspondence question in the way.
    top.flatten(-1, True)

    gds_path = outdir / f"{TOP_CELL}.gds"
    options = db.SaveLayoutOptions()
    options.select_cell(top.cell_index())
    options.format = "GDS2"
    layout.write(str(gds_path), options)

    netlist_path = outdir / f"{TOP_CELL}.spice"
    netlist_path.write_text(REFERENCE_NETLIST)

    return TrivialCell(gds=gds_path, netlist=netlist_path)


def build_bare_cell(outdir: Path, stdcell_gds: Path, cell: str = "clkinv_1") -> Path:
    """Stream one standard cell out on its own -- the untapped control.

    Used to demonstrate *why* ``build()`` adds tie cells: this GDS is the same
    inverter with no taps, and the foundry deck reports DF.13_MV / DF.14_MV
    against it.
    """
    import klayout.db as db

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    layout = db.Layout()
    layout.read(str(stdcell_gds))
    index = layout.cell_by_name(STDCELL_PREFIX + cell)

    path = outdir / f"{STDCELL_PREFIX}{cell}.gds"
    options = db.SaveLayoutOptions()
    options.select_cell(index)
    options.format = "GDS2"
    layout.write(str(path), options)
    return path
