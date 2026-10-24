"""The assembled ``pll_top`` layout (issue #297).

The five block generators under ``layout/pll_top/`` each produce one flat,
standalone GDS cell. This package places those five cells into one top cell,
``pll_top``, and routes the top-level nets of ``design/netlist/pll_top.spice``
between them on Metal4/Metal5, which no block uses.

Modules:

``netlist``   reads the ``pll_top`` instance lines from the committed netlist,
              so the port-to-net map is never typed by hand.
``extract``   chip-level conductor extraction (``klayout.db.LayoutToNetlist``)
              used both to find where a block's port can be reached and to
              check what the finished GDS connects.
``access``    finds, for one block port, a point on that port's own net where a
              via stack up to Metal4 clears every other net in the block.
``route``     draws the top-level wires (Metal4 horizontal tracks, Metal5
              verticals) and refuses any wire that would touch another net.
``assemble``  builds ``pll_top.gds``; ``python3 -m pll_top.top_level.assemble
              --outdir <dir>`` from ``layout/``.
``netcheck``  grades the written GDS: every top-level net joined, no two nets
              shorted, no block-internal net disturbed.
"""
