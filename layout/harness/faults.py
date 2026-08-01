"""Deliberate faults, injected into scratch copies of the trivial cell.

A verification flow that has only ever been shown producing a *clean* result
is not evidence that it can detect a dirty one. These two injections are the
negative controls for the flow: each mutates a throwaway copy of ``inv_tb``
and the run that follows is expected to FAIL. A negative control that comes
back clean is a harness bug, and ``run_pv.py prove`` treats it as one.

Both injections are geometric -- they mutate the *layout*, not the reference
netlist -- so the control exercises the same path a real layout error would.
"""

from __future__ import annotations

from pathlib import Path

# --- DRC fault ---------------------------------------------------------------
# A Metal1 sliver 0.10 um wide, placed in empty space well clear of the row so
# it cannot perturb any other rule by proximity. gf180mcu's minimum Metal1
# width (rule Mn.1) is 0.23 um, so this is an unambiguous width violation.
DRC_FAULT_LAYER = (34, 0)  # Metal1 drawing
DRC_FAULT_BOX_UM = (3.0, 7.0, 3.1, 9.0)  # left, bottom, right, top

# --- LVS fault ---------------------------------------------------------------
# The Metal1 island that is the inverter's output node. Deleting it leaves the
# n-channel and p-channel drains unconnected: the layout no longer has an
# output net joining the two devices, which cannot match the reference
# schematic. Located by the cell's own "ZN" label rather than by hardcoded
# coordinates, so the injection follows the layout if the cell is rebuilt.
LVS_FAULT_LABEL = "ZN"
LVS_FAULT_LABEL_LAYER = (34, 10)  # Metal1 label/pin text


class FaultInjectionError(RuntimeError):
    """Raised when the intended mutation could not be applied."""


def _load(src: Path):
    import klayout.db as db

    layout = db.Layout()
    layout.read(str(src))
    tops = list(layout.top_cells())
    if len(tops) != 1:
        raise FaultInjectionError(f"{src} has {len(tops)} top cells, expected exactly 1")
    return db, layout, tops[0]


def _write(layout, cell, dst: Path) -> Path:
    import klayout.db as db

    dst.parent.mkdir(parents=True, exist_ok=True)
    options = db.SaveLayoutOptions()
    options.select_cell(cell.cell_index())
    options.format = "GDS2"
    layout.write(str(dst), options)
    return dst


def inject_drc_violation(src: Path, dst: Path) -> dict:
    """Add an undersized Metal1 shape. Expected to trip rule ``Mn.1``."""
    db, layout, top = _load(Path(src))
    dbu_per_um = 1.0 / layout.dbu

    layer = layout.layer(*DRC_FAULT_LAYER)
    left, bottom, right, top_um = DRC_FAULT_BOX_UM
    box = db.Box(
        int(round(left * dbu_per_um)),
        int(round(bottom * dbu_per_um)),
        int(round(right * dbu_per_um)),
        int(round(top_um * dbu_per_um)),
    )
    top.shapes(layer).insert(box)
    _write(layout, top, Path(dst))
    return {
        "kind": "drc",
        "description": (
            f"inserted a {right - left:.2f} x {top_um - bottom:.2f} um Metal1 rectangle "
            f"at ({left}, {bottom}) um -- below the 0.23 um minimum Metal1 width"
        ),
        "expected_rule": "Mn.1",
        "path": str(dst),
    }


def inject_lvs_mismatch(src: Path, dst: Path) -> dict:
    """Delete the output-net Metal1 island, opening the shared drain node."""
    db, layout, top = _load(Path(src))

    label_layer = layout.layer(*LVS_FAULT_LABEL_LAYER)
    anchor = None
    for shape in top.shapes(label_layer).each():
        if shape.is_text() and shape.text.string == LVS_FAULT_LABEL:
            anchor = shape.text.trans.disp
            break
    if anchor is None:
        raise FaultInjectionError(
            f"no {LVS_FAULT_LABEL!r} text found on layer "
            f"{LVS_FAULT_LABEL_LAYER[0]}/{LVS_FAULT_LABEL_LAYER[1]} in {src}"
        )

    metal1 = layout.layer(*DRC_FAULT_LAYER)
    point = db.Point(anchor.x, anchor.y)
    removed = 0
    for shape in list(top.shapes(metal1).each()):
        if shape.is_polygon() or shape.is_box() or shape.is_path():
            if shape.polygon.inside(point):
                top.shapes(metal1).erase(shape)
                removed += 1
    if removed == 0:
        raise FaultInjectionError(
            f"no Metal1 polygon covers the {LVS_FAULT_LABEL!r} label at "
            f"({anchor.x}, {anchor.y}) dbu in {src}"
        )

    _write(layout, top, Path(dst))
    return {
        "kind": "lvs",
        "description": (
            f"deleted {removed} Metal1 shape(s) under the {LVS_FAULT_LABEL!r} label -- "
            "the n- and p-channel drains are no longer connected to each other"
        ),
        "expected_result": "netlists do not match",
        "path": str(dst),
    }
