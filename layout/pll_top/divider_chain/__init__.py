"""Real transistor-level layout for the ``divider_chain`` block family
(issue #295).

``design/dff_tg_3v3.sch`` / ``design/div23_cell.sch`` / their leaf cells
(``inv_3v3.sch``, ``tgate_3v3.sch``, ``nand2_3v3.sch``, ``nand3_3v3.sch``,
``nor2_3v3.sch``, ``inv2x_3v3.sch``, ...) are the schematics this family's
layout implements. See ``devgen.py`` for the reusable device-list-driven
leaf-cell generator issue #306 (Part 1 of #295) proves out -- reused/
generalized from ``layout/pll_top/pfd_cp/devgen.py`` (issue #299) -- and
hands to Parts 2-4 (#307-#309: the remaining leaf cells, the ``dff_tg_3v3``
composite, the ``div23_cell`` composite).

Part 2 (#307) added the four remaining combinational leaf cells --
``nand2_3v3``, ``nand3_3v3``, ``nor2_3v3``, ``inv2x_3v3`` -- and, with them,
``devgen.build_row_cell()``: a second generator in the same module for
static gates with real fan-in (3+ terminals on one net), which
``build_stack_cell()`` refuses by design. All four share one fixed row-cell
frame -- identical height, identical ``VDD``/``VSS`` rail y-bands, real
full-width Metal1 rails -- so a composite can abut them in a row. Part 3
(#308) took a different route for ``dff_tg_3v3`` (stack-cell instances side
by side, wired by ``route_net()``/``NetTracks``), so Part 4's
``div23_cell``, which consumes both, has two composition styles available
and must pick or reconcile them -- see
``layout/evidence/divider-rowcells-proof/PROOF.md``'s "Known gap" section,
and ``devgen.py``'s "ROW CELLS" docstring section for the frame itself.
"""
