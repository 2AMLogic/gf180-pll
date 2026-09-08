"""Assemble the ``lock_detector`` block GDS (and its standalone sub-cells).

Flat macro-composition, not GDS-level cell hierarchy (``CellInstArray``): see
``cells.py``'s module docstring. Every ``build_*`` function below returns a
``primitives.Canvas`` with everything already drawn into one top cell, ready
for ``canvas.write_gds(path)`` and ``layout/run_pv.py drc``.
"""

from __future__ import annotations

from pathlib import Path

from . import cells, devices as dev
from .primitives import Canvas, NetTracks, nwell_over, pad_center, route_net, tap_strip


#: DF.13_LV/DF.14_LV cap the distance from any PMOS-in-nwell/NMOS-outside-
#: nwell to its nearest well/substrate tap at 20 um. A design wider than
#: that needs more than one tap pair -- see ``_finish()``.
_TAP_PITCH_UM = 12.0

#: Every "normal" gate row in this package (``inv``/``nand2``/``schmitt`` and
#: everything built from them) sits at these two Y centers, with PMOS/NMOS
#: widths never exceeding these maxima (see ``devices.py``). The periodic
#: tap band is placed relative to *these* constants, not a build's overall
#: bbox -- a single outsized device (``MCW``, ``W=30u``) would otherwise
#: pull every other row's nearest tap tens of microns away. ``MCW``-class
#: outliers get their own dedicated tap instead (see ``build_lock_detector``).
ROW_Y_P = 2.5
ROW_Y_N = -2.5
ROW_W_P_MAX = 2.5
ROW_W_N_MAX = 2.0


def _finish(canvas: Canvas, nets, pwells, block_box, tap_xs=None, *, ntap_net: str = "VDD", ptap_net: str = "VSS"):
    """Common tail: ntap/ptap pair(s), one nwell, route every net once.

    ``tap_xs``, if given, is the set of X positions *known clear* of every
    device's own comp/poly/pad geometry (the gaps between sub-gates a
    hierarchical ``draw_xor2``/``draw_delaywin`` call already returns) --
    this function never invents its own intermediate X positions, because a
    naive evenly-spaced guess has no way to avoid landing inside some
    sub-gate's own footprint (observed directly during bring-up: it doubled
    back to trip M1.2a/M2.2a/M3.2a between a tap's own Metal1 pad/riser and
    an unrelated nearby device's, both correct individually). If omitted,
    one tap pair is placed just past the block's own right edge -- safe for
    any single non-hierarchical cell (``inv``/``nand2``/``schmitt``, always
    well under DF.13_LV/DF.14_LV's 20 um tap-distance cap on their own).

    Placed in a dedicated Y band clear of every row's own comp/poly
    footprint (see ``ROW_Y_P``/``ROW_Y_N`` above).
    """
    x_left, _y_bottom, x_right_edge, _y_top = block_box
    y_p_tap = ROW_Y_P + ROW_W_P_MAX / 2.0 + 1.5
    y_n_tap = ROW_Y_N - ROW_W_N_MAX / 2.0 - 1.5

    xs = list(tap_xs) if tap_xs else [x_right_edge + 1.5]

    ntap_boxes = []
    for x in xs:
        ntap_box, ntap_pad = tap_strip(canvas, "n", x, y_p_tap, ntap_net)
        ptap_box, ptap_pad = tap_strip(canvas, "p", x, y_n_tap, ptap_net)
        ntap_boxes.append(ntap_box)
        nets.setdefault(ntap_net, []).append(pad_center(ntap_pad))
        nets.setdefault(ptap_net, []).append(pad_center(ptap_pad))

    nwell_over(canvas, [*pwells, *ntap_boxes])

    tracks = NetTracks(base_y=block_box[3] + 6.0)
    for net, pads in nets.items():
        route_net(canvas, net, pads, tracks.get(net))


def build_inv_standalone(top_name: str = "lock_detector_inv") -> Canvas:
    canvas = Canvas(top_name)
    nets: dict[str, list[tuple[float, float]]] = {}
    pwells: list[tuple[float, float, float, float]] = []
    box = cells.draw_inv(canvas, nets, pwells, 0.0, 2.5, -2.5, "A", "Y", "VDD", "VSS")
    _finish(canvas, nets, pwells, box)
    return canvas


def build_nand2_standalone(top_name: str = "lock_detector_nand2") -> Canvas:
    canvas = Canvas(top_name)
    nets: dict[str, list[tuple[float, float]]] = {}
    pwells: list[tuple[float, float, float, float]] = []
    box = cells.draw_nand2(canvas, nets, pwells, 0.0, 2.5, -2.5, "A", "B", "Y", "VDD", "VSS")
    _finish(canvas, nets, pwells, box)
    return canvas


def build_schmitt_standalone(top_name: str = "lock_detector_schmitt") -> Canvas:
    canvas = Canvas(top_name)
    nets: dict[str, list[tuple[float, float]]] = {}
    pwells: list[tuple[float, float, float, float]] = []
    box = cells.draw_schmitt(canvas, nets, pwells, 0.0, 2.5, -2.5, "A", "Y", "VDD", "VSS")
    _finish(canvas, nets, pwells, box)
    return canvas


def build_xor2_standalone(top_name: str = "lock_detector_xor2") -> Canvas:
    canvas = Canvas(top_name)
    nets: dict[str, list[tuple[float, float]]] = {}
    pwells: list[tuple[float, float, float, float]] = []
    box, tap_xs = cells.draw_xor2(canvas, nets, pwells, 0.0, 2.5, -2.5, "A", "B", "Y", "VDD", "VSS", prefix="X")
    _finish(canvas, nets, pwells, box, tap_xs=tap_xs)
    return canvas


def build_delaywin_standalone(top_name: str = "lock_detector_delaywin") -> Canvas:
    canvas = Canvas(top_name)
    nets: dict[str, list[tuple[float, float]]] = {}
    pwells: list[tuple[float, float, float, float]] = []
    box, tap_xs = cells.draw_delaywin(canvas, nets, pwells, 0.0, 2.5, -2.5, 14.0, "A", "Y", "VDD", "VSS", prefix="D")
    _finish(canvas, nets, pwells, box, tap_xs=tap_xs)
    return canvas


def build_lock_detector(top_name: str = "lock_detector") -> Canvas:
    """The full ``lock_detector`` block: XERR/XDLY/XNW/XIW/MDNW/MUPW/MCW/XSCH/XILK.

    Wired exactly per ``design/netlist/lock_detector.spice``'s top-level
    ``lock_detector`` subckt. Everything here sits on the ``VDD``/``VSS``
    domain -- there is no ``VDD_DIV``/other-supply net anywhere in this
    module, so there is no way for this block's routing to tie into the
    divider chain's own supply trunk even though the two blocks share the
    ``DIVIDER_LOCK`` floorplan region for physical adjacency only (see
    ``layout/floorplan/skeleton.py`` and this issue's Acceptance Criteria).
    """
    canvas = Canvas(top_name)
    nets: dict[str, list[tuple[float, float]]] = {}
    pwells: list[tuple[float, float, float, float]] = []

    y_p, y_n, y_cap = 2.5, -2.5, 14.0
    vdd, vss = "VDD", "VSS"

    # ``gap_taps`` collects the midpoint of every inter-macro spacer gap
    # below (each one guaranteed clear of any device's own comp/poly/pad
    # geometry, since nothing is ever drawn inside a spacer) alongside the
    # hierarchical ``xor2``/``delaywin`` internal tap_xs, so the periodic
    # ntap/ptap band `_finish()` lays down never has to guess a position --
    # see ``cells.draw_xor2``'s and ``_finish()``'s docstrings for why a
    # naive evenly-spaced guess is unsafe. This whole chain (~85 um, well
    # past DF.13_LV/DF.14_LV's 20 um tap-distance cap) needs many more taps
    # than any single sub-macro on its own.
    gap_taps: list[float] = []

    def _gap(prev_right: float, gap: float) -> float:
        gap_taps.append(prev_right + gap / 2.0)
        return prev_right + gap

    x = 0.0
    b_err, err_taps = cells.draw_xor2(canvas, nets, pwells, x, y_p, y_n, "UP", "DN", "ERR", vdd, vss, prefix="XERR_")
    x = _gap(b_err[2], 3.0)

    b_dly, dly_taps = cells.draw_delaywin(
        canvas, nets, pwells, x, y_p, y_n, y_cap, "ERR", "ERRD", vdd, vss, prefix="XDLY_"
    )
    x = _gap(b_dly[2], 3.0)

    b_nw = cells.draw_nand2(canvas, nets, pwells, x, y_p, y_n, "ERR", "ERRD", "WIDEB", vdd, vss, prefix="XNW_")
    x = _gap(b_nw[2], 3.0)

    b_iw = cells.draw_inv(canvas, nets, pwells, x, y_p, y_n, "WIDEB", "WIDE", vdd, vss, prefix="XIW_")
    x = _gap(b_iw[2], 3.0)

    # XMDNW VWIN WIDE VSS VSS nfet_03v3 L=0.5u W=2u -- gated pull-down.
    mdnw = dev.mdnw_fet("VWIN", "WIDE", vss)
    b_mdnw = cells.draw_discrete_fet(canvas, nets, pwells, x, y_n, mdnw, tab_up=True)
    # No gap tap here (see below): the 1.5 um spacer to MUPW is too tight
    # for a periodic tap's own Metal2/Metal3 riser to clear MUPW's own S/D
    # pad's riser (M2.2a/M3.2a, both plain same-layer spacing rules that
    # apply regardless of net) -- MUPW gets one dedicated tap mid-span
    # instead (see below).
    x = b_mdnw[2] + 1.5

    # XMUPW VWIN VSS VDD VDD pfet_03v3 L=20u W=0.22u -- always-on weak pull-up.
    mupw = dev.mupw_fet("VWIN", vdd, vss)
    b_mupw = cells.draw_discrete_fet(canvas, nets, pwells, x, y_p, mupw, tab_up=False)

    # MUPW's own comp (L=20u) is far wider than DF.13_LV/DF.14_LV's 20 um
    # tap-distance cap on its own, but its S/D pads sit only ~1 um from its
    # own comp edges -- too close for a periodic gap-tap on either side of
    # it (see above). Its middle (clear of both S/D pads and its own
    # centered 0.4x0.4 gate contact tab -- see ``mosfet()``) has plenty of
    # room for one dedicated ntap instead, offset in X from the gate tab so
    # neither PL.5a_LV/PL.5b_LV nor the ordinary poly/comp spacing rules see
    # it.
    mupw_mid_x = (b_mupw[0] + b_mupw[2]) / 2.0 - 4.0
    mupw_ntap_box, mupw_ntap_pad = tap_strip(canvas, "n", mupw_mid_x, ROW_Y_P + ROW_W_P_MAX / 2.0 + 1.5, vdd)
    nets.setdefault(vdd, []).append(pad_center(mupw_ntap_pad))

    # No gap tap on MUPW's far side either, for the same reason as its near
    # side above -- its own drain (VWIN) S/D pad sits ~1 um from the comp
    # edge here too, and MCW (the next device) is NMOS-only (no PMOS, so no
    # extra ntap needed nearby) with its own dedicated ptap already placed
    # next to it below.
    x = max(b_mdnw[2], b_mupw[2]) + 1.5

    # XMCW VSS VWIN VSS VSS nfet_03v3 L=6u W=30u -- integrating MOS cap. Its
    # own X lane is clear of every neighbour, but W=30u puts its own comp
    # far outside DF.14_LV's 20 um tap-distance cap from the ordinary
    # periodic ptap band `_finish()` lays down for the much-narrower normal
    # rows (see ROW_Y_N above) -- so it gets its own dedicated ptap right
    # next to it instead of relying on that band. ``tab_up=True`` (unlike
    # every other NMOS instance in this design) so its gate contact tab
    # grows *up* toward its own dedicated ptap above it, instead of down
    # toward y~24 -- close enough to VDD's own Metal2 bus (the very first,
    # lowest-track net, whose bus necessarily spans this whole block's width
    # at y~25) to trip M2.2a regardless of X, since MCW sits far above the
    # ordinary row band with nothing else nearby to bound its tab's reach.
    y_mcw = 40.0
    mcw = dev.mcw_fet("VWIN", vss)
    b_mcw = cells.draw_discrete_fet(canvas, nets, pwells, x, y_mcw, mcw, tab_up=True)
    mcw_ptap_box, mcw_ptap_pad = tap_strip(canvas, "p", x, y_mcw + mcw.w_um / 2.0 + 1.5, vss)
    nets.setdefault(vss, []).append(pad_center(mcw_ptap_pad))
    x = _gap(max(b_mcw[2], mcw_ptap_box[2]), 3.0)

    b_sch = cells.draw_schmitt(canvas, nets, pwells, x, y_p, y_n, "VWIN", "LOCKB", vdd, vss, prefix="XSCH_")
    x = _gap(b_sch[2], 3.0)

    b_ilk = cells.draw_inv(canvas, nets, pwells, x, y_p, y_n, "LOCKB", "LOCK", vdd, vss, prefix="XILK_")

    block_box = (
        min(b_err[0], b_mcw[0]),
        min(y_n - 1.0, b_mdnw[1]),
        b_ilk[2],
        max(y_cap + 4.0 + 1.0, b_err[3]),
    )
    tap_xs = sorted({*err_taps, *dly_taps, *gap_taps})
    _finish(canvas, nets, pwells, block_box, tap_xs=tap_xs)
    return canvas


_BUILDERS = {
    "inv": build_inv_standalone,
    "nand2": build_nand2_standalone,
    "schmitt": build_schmitt_standalone,
    "xor2": build_xor2_standalone,
    "delaywin": build_delaywin_standalone,
    "lock_detector": build_lock_detector,
}


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", default="/tmp/lock_detector_dev")
    parser.add_argument("--which", default="lock_detector", choices=sorted(_BUILDERS))
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    canvas = _BUILDERS[args.which]()
    gds_path = outdir / f"{canvas.top_name}.gds"
    canvas.write_gds(gds_path)
    print(f"wrote {gds_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
