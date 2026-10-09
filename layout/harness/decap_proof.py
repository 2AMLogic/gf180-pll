"""Minimal-device proof for the VCO decap's device class (issue #759).

``design/netlist/vco.spice`` names the supply decap ``cap_nmos_03v3`` -- the
*non*-``_b`` MOS capacitor, a different device from the loop filter's
``cap_nmos_03v3_b``. Before that class is drawn into the 31,000 um^2 VCO block,
this module draws it alone and lets the PDK's own LVS deck say what it is:

* ``good``      -- one 50 x 50 um device, gate on ``VDD_VCO``, n+ on
  ``GND_VCO``. Must match a one-card reference of class ``cap_nmos_03v3``.
* ``swapped``   -- identical geometry, the two net labels exchanged. The deck's
  capacitor class treats its two terminals as interchangeable, so this *also*
  matches; what distinguishes it is the extracted netlist's terminal order
  (terminal 1 is the poly gate, ``tA => poly2_con``), which the proof records.
* ``no_device`` -- the ``mos_cap_mk`` marker is omitted, so the gate region is
  an ordinary NMOS, not a capacitor. Must **fail**.
* ``class_b``   -- an n-well is added around the comp, which makes the deck
  extract ``cap_nmos_03v3_b``. Must **fail** against the ``cap_nmos_03v3``
  reference.
* ``shorted``   -- the gate row is joined to the n+ bar, so both terminals are
  one net. Must **fail**.

A single isolated capacitor is topologically just "two nets and a cap", so
this cell cannot show an *open* terminal (a floating gate is indistinguishable
from a gate on its own named net). That control needs the surrounding block and
is :func:`block_controls`, run against the assembled ``vco_block``.

    python3 -m harness.decap_proof --outdir DIR      (from ``layout/``)

writes ``DIR/<variant>.gds`` for each variant plus ``DIR/decap_min.spice``,
the shared reference. Running the deck on them is ``run_pv.py lvs``; the exact
commands and results are recorded in
``layout/evidence/vco-layout/decap-20261009/PROOF.md``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

LAYOUT_DIR = Path(__file__).resolve().parents[1]
if str(LAYOUT_DIR) not in sys.path:
    sys.path.insert(0, str(LAYOUT_DIR))

from pll_top.vco import devices as dev  # noqa: E402
from pll_top.vco import primitives as prim  # noqa: E402

TOP = "decap_min"
VARIANTS = ("good", "swapped", "no_device", "class_b", "shorted")
#: Variants LVS must match, and those it must reject.
EXPECT_MATCH = ("good", "swapped")
EXPECT_FAIL = ("no_device", "class_b", "shorted")

BAR_GAP_UM = 1.2  # comp bottom edge -> the Metal1 bar joining the two n+ columns
BAR_WIDTH_UM = 0.8


def reference_netlist() -> str:
    size = dev.DECAP_SIZE_UM
    return (
        f"* One cap_nmos_03v3, {size:g} x {size:g} um: the vco.spice XCDEC1 device alone (issue #759).\n"
        f".subckt {TOP} VDD_VCO GND_VCO\n"
        f"C_XCDEC1 VDD_VCO GND_VCO cap_nmos_03v3 W={size:g}u L={size:g}u\n"
        ".ends\n"
    )


def build(variant: str, outdir: Path) -> Path:
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant {variant!r}; choose from {VARIANTS}")
    canvas = prim.Canvas(TOP)
    size = dev.DECAP_SIZE_UM
    gate_net, diff_net = ("GND_VCO", "VDD_VCO") if variant == "swapped" else ("VDD_VCO", "GND_VCO")
    # Room below the device for the gate row and the n+ bar.
    x0, y0 = 5.0, 5.0
    cap = prim.mos_cap_nmos(canvas, size, size, x0, y0, gate_ends=("bottom",))
    comp = cap.comp

    if variant == "no_device":
        _erase(canvas, "mos_cap_mk")
        _erase(canvas, "lvpwell")
    if variant == "class_b":
        e = 0.6
        canvas.rect("nwell", comp[0] - e, comp[1] - e, comp[2] + e, comp[3] + e)

    # n+ bar: both columns carried down past the gate row, joined below it.
    bar_y1 = cap.rows["bottom"][1] - BAR_GAP_UM
    bar_y0 = bar_y1 - BAR_WIDTH_UM
    for col in cap.cols:
        canvas.rect("metal1", col[0], bar_y0, col[2], col[1])
    canvas.rect("metal1", cap.cols[0][0], bar_y0, cap.cols[1][2], bar_y1)
    canvas.pin(diff_net, cap.cols[0][0], bar_y0, cap.cols[1][2], bar_y1)

    row = cap.rows["bottom"]
    canvas.pin(gate_net, *row)
    if variant == "shorted":
        mid = (row[0] + row[2]) / 2.0
        canvas.rect("metal1", mid - 0.3, bar_y1, mid + 0.3, row[1])

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / f"{variant}.gds"
    canvas.write_gds(path)
    return path


def block_controls(src: Path, outdir: Path) -> dict:
    """Mutated copies of the assembled ``vco_block.gds`` that LVS must reject.

    * ``decap_missing`` -- the upper decap's comp, poly, n+ and marker are
      deleted: one of the two ``cap_nmos_03v3`` is absent from extraction.
    * ``gate_open`` -- every Via1 inside the upper decap's gate row is deleted,
      so that device's gate no longer reaches ``VDD_VCO`` (an open terminal).
    * ``diff_open`` -- the Metal1 bar joining the two decaps' n+ columns is
      deleted, so the n+ side no longer reaches ``GND_VCO``.

    Returns ``{name: path}``. Coordinates come from ``block.decap_plan()``.
    """
    import klayout.db as db  # noqa: PLC0415

    from pll_top.vco import block as vco_block  # noqa: PLC0415

    dp = vco_block.decap_plan()
    upper = dp.comps[1]
    out = {}
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    def mutate(name: str, edits: dict[str, tuple[float, float, float, float]]) -> None:
        layout = db.Layout()
        layout.read(str(src))
        top = layout.top_cell()
        for layer, box in edits.items():
            li = layout.layer(*prim.LAYER[layer])
            cut = db.Region(db.Box(*[round(v / layout.dbu) for v in box]))
            shapes = top.shapes(li)
            keep = db.Region(shapes) - cut
            shapes.clear()
            shapes.insert(keep)
        opts = db.SaveLayoutOptions()
        opts.format = "GDS2"
        path = outdir / f"{name}.gds"
        layout.write(str(path), opts)
        out[name] = path

    pad = 1.0
    ub = (upper[0] - pad, upper[1] - pad, upper[2] + pad, upper[3] + pad)
    mutate(
        "decap_missing",
        {k: ub for k in ("comp", "poly2", "nplus", "mos_cap_mk", "lvpwell")},
    )
    row_y = dp.gate_row_y[1]
    mutate("gate_open", {"via1": (upper[0], row_y - 1.0, upper[2], row_y + 1.0)})
    bar = dp.bar
    mutate("diff_open", {"metal1": (upper[0] - 0.5, bar[1], bar[2] - 2.0, bar[3])})
    return out


def _erase(canvas: prim.Canvas, layer: str) -> None:
    canvas.top.shapes(canvas.layout.layer(*prim.LAYER[layer])).clear()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--outdir", required=True)
    args = parser.parse_args(argv)
    out = Path(args.outdir)
    for v in VARIANTS:
        print(f"wrote {build(v, out)}")
    ref = out / f"{TOP}.spice"
    ref.write_text(reference_netlist())
    print(f"wrote {ref}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
