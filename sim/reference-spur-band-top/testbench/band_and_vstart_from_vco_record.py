#!/usr/bin/env python3
"""Where this campaign's per-corner VCO band code and release voltage come from.

`sim/reference-spur` measures the closed-loop reference spur at ONE operating
point: f_ref = 25 MHz, N = 6, f_out = **150 MHz**, VCO band 6. The spur grows
with output frequency (`theta = 2*pi*f_out*TIE`), so `spec/pll.md`'s
<= -55 dBc line binds at the **200 MHz** ceiling of the ratified output band,
and that record reports its 200 MHz figure as arithmetic -- `spur_dbc +
2.50 dB` -- rather than as a measurement. At two corners that arithmetic lands
on the wrong side of the line. This campaign is the same measurement taken AT
200 MHz, so that the binding number is a measured one.

Moving to 200 MHz is not a one-parameter change, and this script is where the
arithmetic that decides the rest of it is written down.

**The band code is not a free choice.** `spec/pll.md`'s band-selection rule
(normative, from DR-003 Decision 4) says a system targeting output frequency
`f` must configure **the lowest 3-bit band code that reaches `f`**, inside the
DR-003 Decision 5 control-voltage window of 0.9-2.7 V. Applied to
`sim/vco-tuning-range`'s committed f(Vctrl) table at 200 MHz, that rule does
not select one code for the whole grid:

- **band 6 at 34 of the 45 PVT points**, and
- **band 7 at the remaining 11** -- the cold and/or high-supply points where
  band 6's curve tops out below 200 MHz.

That split is *why this campaign has to exist as a sibling* rather than as one
more corner of `sim/reference-spur`: at 150 MHz one static code (6) covers all
45 corners, which is exactly what let that campaign hold its band fixed and
its `b*_code` bits in `params`; at 200 MHz no single code does, so the band
bits are a per-point sweep axis here.

**The release voltage follows from the band** -- the control voltage at which
that corner's curve, in that corner's rule-selected band, reaches
`N*f_ref = 200 MHz`. As in `sim/reference-spur`, the loop's slow closed-loop
pole is 1/(R*C1) = 9.3 us and a common release voltage would spend tens of
microseconds slewing at Icp/C1 = 14 mV/us before any spectral window could
open.

    python3 band_and_vstart_from_vco_record.py            # the table tb.json carries
    python3 band_and_vstart_from_vco_record.py --check    # ... and diff it against tb.json
    python3 band_and_vstart_from_vco_record.py --emit     # regenerate tb.json's sweeps.op + grid

It reads only committed CSV and committed JSON. No simulator, no PDK, no
network.

**None of the arithmetic is re-implemented here.** The rule, the point ids,
the grid emission and the `--check` diff are loaded from
`sim/period-jitter-band-top/testbench/band_and_vstart_from_vco_record.py`,
which in turn loads the f(Vctrl) interpolation from
`sim/reference-spur/testbench/vstart_from_vco_record.py`. Two campaigns now
run the mandated PVT matrix at the same 200 MHz binding point, and they are
physically incapable of disagreeing about which band the ratified rule selects
there or about where that band's committed curve crosses 200 MHz -- a property
that matters more than the small amount of code it saves, because the two
campaigns' numbers will be read against each other.

Nothing downstream trusts the release voltages to be right. The release point
only decides where the loop STARTS; every reported quantity is measured after
the loop has closed on its own lock point, the residual that remains is itself
measured and reported per point as `drift_q_fc`, and a point whose estimate
missed badly enough to leave the loop unlocked fails this manifest's
`ferr`/`ferr_fb`/`fout`/`nmeas` lock checks and is reported as a failing point,
never as a spur number. The band code is different in kind -- it is a real
static configuration input of the part, not an estimate -- which is why it is
derived from the ratified rule rather than from convenience, and why `--check`
refuses a manifest that has drifted from it.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SIM = HERE.parents[1]

sys.path.insert(0, str(SIM))
from harness.derived import load_module  # noqa: E402

_rule = load_module(
    SIM / "period-jitter-band-top" / "testbench" / "band_and_vstart_from_vco_record.py"
)

#: The committed VCO characterization every band/vstart here is read out of,
#: re-exported so a reader (and the tests) can see which record this campaign
#: is anchored to without following two hops of imports.
VCO_RECORD = _rule.VCO_RECORD
VCTRLS = _rule.VCTRLS
BAND_CODES = _rule.BAND_CODES
KVCO_BOUND_HZ_PER_V = _rule.KVCO_BOUND_HZ_PER_V

interp_vctrl = _rule.interp_vctrl
load_curves = _rule.load_curves
kvco_at = _rule.kvco_at
select_band = _rule.select_band
point_id = _rule.point_id
derive_table = _rule.derive_table
declared_map = _rule.declared_map
emit = _rule.emit


def main():
    return _rule.main(HERE / "tb.json", doc=__doc__)


if __name__ == "__main__":
    raise SystemExit(main())
