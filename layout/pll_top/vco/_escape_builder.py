"""Shared Metal1 escape / rail-tie construction for the VCO block's two
mesh-routed ``_Builder`` classes.

``vtoi_core.py`` and ``mirror.py`` each route every inter-device net as a
Metal2 track in the channel between an NMOS row and a PMOS row, with Metal1
only for the short vertical escape from a device pad up/down to its track
(see either module's own docstring for the "mesh, not a chain" rationale).
Four pieces of that construction -- ``escape``, ``jog_escape``, ``rail_stub``,
``_y_bottom`` -- used to be duplicated verbatim between the two ``_Builder``
classes, differing only in one respect: ``mirror.py`` supports more than one
device bank (``BankPlan``, issue #324's fold), while ``vtoi_core.py`` has
exactly one implicit bank. This module factors the shared construction into
one place; each ``_Builder`` mixes in ``EscapeBuilderMixin`` and passes a
``bank`` object satisfying ``EscapeBank`` below -- ``mirror.py`` passes a real
``BankPlan``, ``vtoi_core.py`` passes its own single ``Plan``, which carries
the same ``index``/``pmos_top``/``nmos_bottom``/``track_y`` a one-bank
stand-in would need.

``draw_fet``, ``draw_cc_array`` and every other per-device-topology decision
stay in each module: they diverge in real ways (multi-finger devices in
``vtoi_core.py`` vs. multi-bank rail routing and common-centroid arrays in
``mirror.py``) and are not part of this shared construction.
"""

from __future__ import annotations

from typing import Protocol

from . import primitives as prim


class EscapeReservePlan(Protocol):
    def reserve(self, net: str, x0: float, y0: float, x1: float, y1: float) -> None: ...


class EscapeBank(Protocol):
    """Bank-scoped geometry ``escape()``/``_y_bottom()`` need: which track a
    net's column lands on, and where a device row's own bottom edge sits.

    ``mirror.py``'s real ``BankPlan`` already has all three; ``vtoi_core.py``
    (exactly one implicit bank) satisfies this by giving its own ``Plan`` the
    same ``index``/``nmos_bottom`` fields (``pmos_top`` and ``track_y`` it
    already had) and passing itself as the ``bank``.
    """

    index: int
    pmos_top: float
    nmos_bottom: float

    def track_y(self, net: str, row: str) -> float: ...


class EscapeBuilderMixin:
    """Mix into a ``_Builder`` that has already set, before any of these
    methods are called: ``self.canvas`` (the ``primitives.Canvas`` these draw
    into), ``self.plan`` (an ``EscapeReservePlan``), ``self.net_x`` (a dict
    accumulating drawn escape x-coordinates, keyed ``(net, bank.index,
    row)``), and ``self.escape_wire_w_um`` (the Metal1 escape wire width).
    """

    canvas: prim.Canvas
    plan: EscapeReservePlan
    net_x: dict
    escape_wire_w_um: float

    def escape(self, net: str, x: float, y_pad_edge: float, row: str, bank: EscapeBank) -> None:
        """Metal1 column from a device pad edge to ``net``'s Metal2 track.

        ``bank`` selects *which* channel's track: every bank runs its own
        lo/hi track pair per net, and a column only ever reaches the channel
        of the bank whose device row it starts in.
        """
        y_track = bank.track_y(net, row)
        y0, y1 = min(y_pad_edge, y_track), max(y_pad_edge, y_track)
        half = self.escape_wire_w_um / 2.0
        self.plan.reserve(net, x - half, y0, x + half, y1)
        prim.v_wire(self.canvas, x, y0, y1, width=self.escape_wire_w_um)
        prim.via1_stack(self.canvas, x, y_track)
        self.net_x.setdefault((net, bank.index, row), []).append(x)

    def jog_escape(
        self, net: str, pad: tuple, x_jog: float, row: str, bank: EscapeBank
    ) -> None:
        """As ``escape()``, for a terminal whose pad faces the wrong way.

        Runs Metal1 sideways out of the pad first, at the pad's own height
        (so the joint is a full-width overlap, not a notch), then drops the
        column from there.
        """
        y_c = (pad[1] + pad[3]) / 2.0
        width = pad[3] - pad[1]
        half = self.escape_wire_w_um / 2.0
        prim.h_wire(self.canvas, pad[0], x_jog + half, y_c, width=width)
        self.plan.reserve(net, min(pad[2], x_jog - half), pad[1], x_jog + half, pad[3])
        self.escape(net, x_jog, y_c, row, bank)

    def rail_stub(self, net: str, x: float, y_from: float, y_to: float) -> None:
        """Plain Metal1 stub from a source pad to the block's own rail band."""
        y0, y1 = min(y_from, y_to), max(y_from, y_to)
        half = self.escape_wire_w_um / 2.0
        self.plan.reserve(net, x - half, y0, x + half, y1)
        prim.v_wire(self.canvas, x, y0, y1, width=self.escape_wire_w_um)

    def _y_bottom(self, row: str, height_um: float, bank: EscapeBank) -> float:
        """An item's own bottom edge for a footprint ``height_um`` tall.

        Bottom-aligned in an NMOS row, top-aligned in a PMOS one -- ``row``
        picks which; ``height_um`` is the item's full drawn footprint height
        (one row for a plain fet, an R-row footprint for a common-centroid
        array), not a gate length, so this works unchanged for both callers.
        """
        if row == "pfet":
            return bank.pmos_top - height_um
        return bank.nmos_bottom
