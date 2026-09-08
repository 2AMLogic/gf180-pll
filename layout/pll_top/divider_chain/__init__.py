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
"""
