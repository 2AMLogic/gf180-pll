"""gf180-pll :: period-jitter-band-top :: period/TIE reduction, reused verbatim.

This campaign measures the same physical quantity as `sim/period-jitter` --
the deterministic, control-ripple-driven period-to-period spacing of the
locked output -- at the 200 MHz top of the ratified band instead of at
150 MHz. The *reduction* from waveform to number is therefore not merely
similar to that campaign's, it must be identical, or the two campaigns'
numbers would not be comparable and the whole point of running this one
(what does moving to the top of the band do to the jitter?) would be lost.

So this module loads `sim/period-jitter/testbench/derive.py` rather than
copying it -- the same cross-directory `load_module` reuse
`sim/period-jitter` itself already uses for `sim/vco-tuning-range`'s
`_numeric.py`, and for the same reason. `sim/tests/test_period_jitter_derive.py`
replays a synthetic waveform of known jitter through that exact code path off
any simulator; pinning to the same file means that test covers this campaign
too, rather than covering a copy of it that could drift.

Nothing is redefined here. `extract_period_jitter`, `derive_point` and
`derive_tables` are the sibling campaign's, unmodified, and both frequency-
agnostic: every quantity they compute (period jitter as a percentage of the
*measured* period, TIE against the sequence's own least-squares line) is
normalized by the waveform itself, not by any assumed nominal frequency.
"""

from __future__ import annotations

import sys
from pathlib import Path

SIM = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SIM))
from harness.derived import load_module  # noqa: E402

_base = load_module(SIM / "period-jitter" / "testbench" / "derive.py")

#: The floor on crossings before a channel's statistics mean anything, and the
#: draft (unratified, #1) target the verdict column is read against -- both
#: inherited, not restated, so a change to the sibling campaign's reduction
#: cannot leave this campaign silently reading against a different line.
MIN_CROSSINGS = _base.MIN_CROSSINGS
DRAFT_TJ_RMS_PCT = _base.DRAFT_TJ_RMS_PCT

extract_period_jitter = _base.extract_period_jitter
derive_point = _base.derive_point
derive_tables = _base.derive_tables
