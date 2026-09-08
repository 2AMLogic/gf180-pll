"""PLL block-placement floorplan (issue #17).

``PLL-FLOORPLAN.md`` is the floorplan record itself (isolation, supply
routing, loop-filter placement, matching-critical cells, area budget).
``skeleton.py`` assembles the GDS block-placement skeleton that record
describes; see that module's docstring for why it is drawn on GDS layer
(0, 0) and what running it through the DRC flow does and does not prove.
"""

from __future__ import annotations

__all__ = ["skeleton"]
