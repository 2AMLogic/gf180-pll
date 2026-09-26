#!/usr/bin/env python3
"""Regression guard for ``_canvas.NetTracks``' Metal2 ``pitch`` binding
(issue #432, a follow-up to the #429/PR #430 consolidation).

``lock_detector/primitives.py``, ``divider_chain/devgen.py``,
``pfd_cp/cp_array.py`` and ``pfd_cp/cp_dumpbuf.py`` each used to define their
own byte-identical ``NetTracks`` class whose ``pitch`` defaulted to a
*reference* to that module's own ``METAL2_TRACK_PITCH_UM``. After the four
copies were consolidated into ``pll_top/_canvas.py`` they all alias one shared
class whose default is the bare literal ``0.75``, so that reference -- and with
it the automatic propagation of a later constant edit -- is gone.

Nothing misbehaves today: all four constants are 0.75. The hazard is the
*next* edit. If one module's ``METAL2_TRACK_PITCH_UM`` is raised for a DRC
reason, ``NetTracks`` keeps handing out 0.75 um tracks and the divergence
surfaces only as a Metal2 spacing violation in generated geometry -- the exact
failure the class exists to prevent by construction (see its docstring in
``_canvas.py``). This file turns that "they happen to be equal" comment at the
four alias sites into an assertion, per this repo's no-claim-without-a-testbench
rule.

No PDK, no KLayout and no PV environment needed: ``_canvas`` imports
``klayout.db`` lazily (inside ``Canvas.__post_init__``), and nothing here
builds a canvas.

    python3 -m unittest discover -s layout/tests -t layout/tests -v

IF THIS TEST FAILS after you deliberately changed one module's
``METAL2_TRACK_PITCH_UM``: do not "fix" it by editing the expectation. The
shared allocator no longer matches that module, so bind the pitch explicitly
at that module's ``NetTracks(...)`` call sites (or re-introduce a per-module
binding, e.g. ``NetTracks = partial(_canvas.NetTracks,
pitch=METAL2_TRACK_PITCH_UM)``) before relaxing anything here.
"""

from __future__ import annotations

import inspect
import unittest

from _env import LAYOUT_DIR  # noqa: F401

from pll_top import _canvas  # noqa: E402
from pll_top.divider_chain import devgen  # noqa: E402
from pll_top.lock_detector import primitives  # noqa: E402
from pll_top.pfd_cp import cp_array, cp_dumpbuf, rowgen  # noqa: E402

#: Every module that aliases ``_canvas.NetTracks`` *and* defines its own
#: ``METAL2_TRACK_PITCH_UM``. ``pfd_cp/rowgen.py`` is deliberately absent --
#: see ``RowgenPitchIsUnrelatedTests`` below.
NETTRACKS_MODULES = (
    ("divider_chain.devgen", devgen),
    ("lock_detector.primitives", primitives),
    ("pfd_cp.cp_array", cp_array),
    ("pfd_cp.cp_dumpbuf", cp_dumpbuf),
)


def _shared_pitch_default() -> float:
    """The ``pitch`` default baked into the one shared ``NetTracks`` class."""
    return inspect.signature(_canvas.NetTracks.__init__).parameters["pitch"].default


class SharedNetTracksPitchTests(unittest.TestCase):
    """The shared allocator's pitch default still equals every consumer's own
    ``METAL2_TRACK_PITCH_UM`` -- the property the pre-consolidation copies had
    by construction."""

    def test_shared_default_is_a_number(self):
        # Guards the introspection itself: a future signature change (pitch
        # made keyword-only, renamed, or turned into a required parameter)
        # must not silently turn the assertions below into no-ops against
        # inspect.Parameter.empty.
        default = _shared_pitch_default()
        self.assertIsInstance(default, float)

    def test_every_module_constant_matches_the_shared_default(self):
        default = _shared_pitch_default()
        for name, module in NETTRACKS_MODULES:
            with self.subTest(module=name):
                self.assertEqual(
                    module.METAL2_TRACK_PITCH_UM,
                    default,
                    f"{name}.METAL2_TRACK_PITCH_UM "
                    f"({module.METAL2_TRACK_PITCH_UM}) no longer equals "
                    f"_canvas.NetTracks' pitch default ({default}); that "
                    f"module's NetTracks would hand out {default} um tracks "
                    f"while the rest of its geometry assumes "
                    f"{module.METAL2_TRACK_PITCH_UM} um -- bind pitch at that "
                    f"module's NetTracks call sites, see this file's docstring",
                )

    def test_every_module_alias_is_the_shared_class(self):
        # If a module ever re-defines its own NetTracks instead of aliasing
        # the shared one, the assertion above stops describing what that
        # module actually instantiates.
        for name, module in NETTRACKS_MODULES:
            with self.subTest(module=name):
                self.assertIs(module.NetTracks, _canvas.NetTracks)

    def test_allocated_tracks_are_spaced_by_the_module_constant(self):
        # The behavioural form of the same invariant: what each module's
        # alias actually hands out, not just what its signature says.
        for name, module in NETTRACKS_MODULES:
            with self.subTest(module=name):
                tracks = module.NetTracks(base_y=0.0)
                first = tracks.get("net_a")
                second = tracks.get("net_b")
                self.assertEqual(first, 0.0)
                self.assertAlmostEqual(
                    second - first, module.METAL2_TRACK_PITCH_UM, places=9
                )
                # Same net twice is the same track (the allocator's whole point).
                self.assertEqual(tracks.get("net_a"), first)


class RowgenPitchIsUnrelatedTests(unittest.TestCase):
    """``pfd_cp/rowgen.py``'s 0.8 um ``METAL2_TRACK_PITCH_UM`` is a separate
    constant for a different helper, not a fifth value of the one above."""

    def test_rowgen_does_not_consume_nettracks(self):
        # This is what licenses rowgen's exclusion from NETTRACKS_MODULES:
        # it never instantiates the shared allocator, so its own pitch is
        # free to differ. If rowgen ever grows a NetTracks alias, this fails
        # and the exclusion above has to be re-justified.
        self.assertFalse(hasattr(rowgen, "NetTracks"))

    def test_rowgen_pitch_is_deliberately_different(self):
        self.assertNotEqual(
            rowgen.METAL2_TRACK_PITCH_UM, _shared_pitch_default()
        )


if __name__ == "__main__":
    unittest.main()
