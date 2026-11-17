"""The one shared home for gf180mcu DRC rule values the ``layout/pll_top/*``
blocks may not disagree about (issue #922).

CO.1 pins the contact size as a minimum *and* a maximum -- 0.22 um square;
gf180mcu contacts are not resizable, so no block can ever be right drawing
any other size. Until this module existed that number was transcribed by
hand six times across the block generators, under three different public
names (``DRC_CONTACT_SIZE_UM``, ``CONTACT_SIZE_UM``, ``CONTACT_UM``), with
no import, no derivation, and no test comparing any two of them -- a typo
in one copy, or a rule revision applied to five of six, would surface only
as a DRC failure on that one block. Named with the same leading-underscore
package-private convention as ``_canvas.py`` (issue #317), the sibling
shared home this module follows.

Scope: rule values the PDK fixes *exactly*, only. The per-block chosen
margins above rule minima -- ``VIA_ENCLOSURE_UM`` (0.09 in four modules,
deliberately 0.06 in ``lock_detector/primitives.py``),
``CONTACT_PITCH_UM``, ``CONTACT_ROW_MARGIN_UM``, ``IMPLANT_MARGIN_UM``,
``NWELL_MARGIN_UM`` -- legitimately differ or carry per-block headroom, so
they stay in each block's own module and keep being passed into the shared
``_canvas`` helpers as explicit keyword arguments, exactly that module's
documented design. CO.1 is the one constant in that set that is a rule
value rather than a margin, which is why it lives here and they do not.

Every importing module keeps its own public constant name, bound to the
one definition here -- the same compatibility tactic ``_canvas.py`` used
for ``Canvas``: ``DRC_CONTACT_SIZE_UM`` in ``vco/devices.py`` and
``lock_detector/devices.py``, ``CONTACT_SIZE_UM`` in ``pfd_cp/devgen.py``,
``pfd_cp/rowgen.py`` and ``divider_chain/devgen.py``, ``CONTACT_UM`` in
``loop_filter/primitives.py`` -- so no call site or test changes.
"""

from __future__ import annotations

#: gf180mcu rule CO.1: contact size, minimum *and* maximum (0.22 um
#: square). Contacts are not resizable, so this is a hard constant, not a
#: derived margin.
CONTACT_SIZE_UM = 0.22
