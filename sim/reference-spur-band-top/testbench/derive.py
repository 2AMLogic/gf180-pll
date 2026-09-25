"""gf180-pll :: reference-spur-band-top :: spectral reduction, reused verbatim.

This campaign measures the same physical quantity as `sim/reference-spur` --
the pair of sidebands at +/- f_ref around the carrier of the locked output --
at the 200 MHz binding top of the ratified output band instead of at 150 MHz.
The *reduction* from waveform to number is therefore not merely similar to
that campaign's, it must be identical, or the two campaigns' numbers would not
be comparable and the question this one exists to answer -- what does the
measured spur do at the frequency the spec line actually binds at? -- would
not be answerable by laying the two tables side by side.

So this module loads `sim/reference-spur/testbench/derive.py` rather than
copying it, the same cross-directory `load_module` reuse
`sim/period-jitter-band-top` uses for its own sibling's reduction.
`sim/tests/test_reference_spur_derive.py` replays synthetic waveforms of known
phase deviation (-45, -55, -61, -65 dBc) through that exact code path off any
simulator, and pins its spectral floor and its zero-drift extrapolation;
pinning to the same file means that test covers this campaign too, rather than
covering a copy of it that could drift.

Nothing is redefined here, and in particular the 200 MHz column is not: the
shared reduction reads the run's own declared operating point (`nratio*fref`)
and scales by `20*log10(200 MHz / f_out)`, which is +2.50 dB for
`sim/reference-spur`'s 150 MHz runs and exactly 0.00 dB here. So
`spur_dbc_at_200mhz` is arithmetic in that campaign's records and is the
measurement itself in this one -- and the table's own notes say which, per
run, rather than leaving a reader to work it out from the manifest.
"""

from __future__ import annotations

import sys
from pathlib import Path

SIM = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SIM))
from harness.derived import load_module  # noqa: E402

_base = load_module(SIM / "reference-spur" / "testbench" / "derive.py")

#: The spec line the verdict column is read against, and the binding output
#: frequency it is stated at -- both inherited, not restated, so a change to
#: the sibling campaign's reduction cannot leave this campaign silently
#: scoring against a different line.
SPUR_TARGET_DBC = _base.SPUR_TARGET_DBC
F_OUT_BINDING = _base.F_OUT_BINDING

derive_point = _base.derive_point
derive_tables = _base.derive_tables
