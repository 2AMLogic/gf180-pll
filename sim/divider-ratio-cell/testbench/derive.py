"""divider-ratio-cell's reduction: sign-correct the div2/div3 output pulse widths.

Ports the awk correction ``sim/divider-ratio/testbench/run.sh`` (pre-harness)
applied: ``.measure`` computes ``pw = fall#3 - rise#3``, which comes out
negative when the DC operating point happens to start the cell high (rise #3
and fall #3 then land one output period apart in the other order). Adding
back one output period is exact, not a fudge -- the two edges are still the
correct high pulse, just read in the wrong order.
"""

from __future__ import annotations


def derive_point(point):
    kf = point.params.get("kf")
    if kf is None:
        return {}
    tvco = 1.0 / float(kf)

    pwa = point.get("pwa")
    pw_div2 = None if pwa is None else (pwa + 2 * tvco if pwa < 0 else pwa)

    pwb = point.get("pwb")
    pw_div3 = None if pwb is None else (pwb + 3 * tvco if pwb < 0 else pwb)

    out = {}
    if pw_div2 is not None:
        out["pw_div2_s"] = pw_div2
    if pw_div3 is not None:
        out["pw_div3_s"] = pw_div3
    return out
