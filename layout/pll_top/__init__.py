"""Real per-block physical layout for the PLL (issue #292 / #293).

Sub-packages here draw actual transistor-level GDS geometry for the PLL's
blocks, as opposed to ``layout/floorplan/skeleton.py``'s block-placement
*boundary rectangles*. See ``layout/pll_top/vco/`` for the first block
(issue #293).
"""
