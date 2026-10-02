#!/usr/bin/env python3
"""Per-bundle static-band-code coverage of the Output band ceiling (issue #534).

`spec/pll.md`'s Output band row was ratified as 10 - 200 MHz as a per-operating-
point *envelope*: at every PVT point some band reaches 200 MHz. The band code,
though, is a static configuration input (DR-001 Decision 2) -- nothing on-chip
re-selects it as temperature or supply move. This script asks the question the
envelope claim does not: for ONE static code in ONE process bundle, which
frequencies stay reachable across that bundle's whole temperature x supply box
(3 temperatures x 3 supplies = 9 points)?

"Reaches f" is the band-selection rule's own meaning: the committed f(Vctrl)
curve of that band at that point brackets f inside the 0.9 - 2.7 V control
window (DR-003 Decision 5), i.e. f1 <= f <= f7 in the committed record. For a
code b over a set of points, the frequencies held at every point are therefore
[max f1, min f7] -- the maximum of the band floors and the minimum of the band
ceilings -- empty if max f1 > min f7.

    python3 static_band_coverage.py            # print the tables
    python3 static_band_coverage.py --check    # exit 1 if the 200 MHz finding
                                               # of #534 does not re-derive

Reads only the committed CSV the other band/vstart scripts read. No simulator,
no PDK, no network. The curve loading and "reaches" test are
`sim/reference-spur/testbench/vstart_from_vco_record.py`'s, not re-implemented.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SIM = HERE.parents[1]

sys.path.insert(0, str(SIM))
from harness.derived import load_module  # noqa: E402

_vs = load_module(SIM / "reference-spur" / "testbench" / "vstart_from_vco_record.py")
VCO_RECORD = _vs.VCO_RECORD
interp_vctrl = _vs.interp_vctrl
load_curves = _vs.load_curves

BUNDLES = ("typical", "ff", "ss", "fs", "sf")
BANDS = tuple(range(8))
TARGET_HZ = 200e6


def curves():
    """{band: {(bundle, temp, vdd): [f1..f7]}} for the five MOS bundles."""
    out = {}
    for b in BANDS:
        out[b] = {k: v for k, v in load_curves("band%d" % b).items() if k[0] in BUNDLES}
    return out


def keys_of(c, bundle=None):
    return sorted(k for k in c[0] if bundle is None or k[0] == bundle)


def reach_count(c, band, keys, f):
    return sum(1 for k in keys if interp_vctrl(c[band][k], f) is not None)


def window(c, band, keys):
    """(max floor, min ceiling) of `band` over `keys`, with the points binding each."""
    lo = max(keys, key=lambda k: c[band][k][0])
    hi = min(keys, key=lambda k: c[band][k][-1])
    return c[band][lo][0], lo, c[band][hi][-1], hi


def best_static(c, keys):
    """Highest frequency one static code holds over `keys`: (f_hz, band, binding key)."""
    best = None
    for b in BANDS:
        flo, _, fhi, khi = window(c, b, keys)
        if flo <= fhi and (best is None or fhi > best[0]):
            best = (fhi, b, khi)
    return best


def merge(ivs):
    out = []
    for a, z in sorted(ivs):
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], z))
        else:
            out.append((a, z))
    return out


def intersect(xs, ys):
    return [(max(a, c_), min(z, d)) for a, z in xs for c_, d in ys if max(a, c_) <= min(z, d)]


def ceiling(ivs, cap=TARGET_HZ):
    """Highest frequency <= cap inside the interval set."""
    return max(min(z, cap) for a, z in ivs if a <= cap)


def holes(ivs, lo, hi):
    out, at = [], lo
    for a, z in sorted(ivs):
        if a > at and at < hi:
            out.append((at, min(a, hi)))
        at = max(at, z)
    return out


def fmt(k):
    return "%s/%g C/%.2f V" % k


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    c = curves()
    allkeys = keys_of(c)
    assert len(allkeys) == 45, len(allkeys)
    print("VCO record %s; %d PVT points (5 bundles x 3 T x 3 V)\n" % (VCO_RECORD, len(allkeys)))

    print("Coverage of %.0f MHz by a single static code (points reached, of 9 per bundle)"
          % (TARGET_HZ / 1e6))
    print("| bundle | band 6 | band 7 | any single code reaches all 9? |")
    print("|---|---|---|---|")
    table = {}
    for bu in BUNDLES:
        ks = keys_of(c, bu)
        n6, n7 = (reach_count(c, b, ks, TARGET_HZ) for b in (6, 7))
        allcodes = [b for b in BANDS if reach_count(c, b, ks, TARGET_HZ) == len(ks)]
        table[bu] = (n6, n7, allcodes)
        print("| `%s` | %d of %d | %d of %d | %s |" % (
            bu, n6, len(ks), n7, len(ks),
            "yes - band %s" % ", ".join(map(str, allcodes)) if allcodes else "**no**"))

    n6only = n7only = either = 0
    for k in allkeys:
        r6 = interp_vctrl(c[6][k], TARGET_HZ) is not None
        r7 = interp_vctrl(c[7][k], TARGET_HZ) is not None
        either += r6 and r7
        n7only += r7 and not r6
        n6only += r6 and not r7
        assert r6 or r7, k
    print("\nOver 45 points: %d reached by band 6 or 7, %d only by band 7, %d only by band 6"
          % (either, n7only, n6only))

    print("\nFrequencies held by ONE static code over the whole box, per bundle")
    print("(union over codes of [max band floor, min band ceiling] across the 9 points, MHz)")
    held = {}
    for bu in BUNDLES:
        ks = keys_of(c, bu)
        ivs = merge([window(c, b, ks)[::2] for b in BANDS if window(c, b, ks)[0] <= window(c, b, ks)[2]])
        held[bu] = ivs
        print("- `%s`: %s" % (bu, "; ".join("%.1f-%.1f" % (a / 1e6, z / 1e6) for a, z in ivs)))

    common = held[BUNDLES[0]]
    for bu in BUNDLES[1:]:
        common = intersect(common, held[bu])
    print("\nHeld by a static code in EVERY bundle: %s"
          % "; ".join("%.1f-%.1f" % (a / 1e6, z / 1e6) for a, z in common))

    print("\nDerated ceiling: highest frequency <= %.0f MHz that one static code holds" % (TARGET_HZ / 1e6))
    print("| scope | derated ceiling (MHz) |")
    print("|---|---|")
    for bu in BUNDLES:
        print("| `%s` alone | %.1f |" % (bu, ceiling(held[bu]) / 1e6))
    cc = ceiling(common)
    print("| every bundle (the figure the Output band row carries) | %.1f |" % (cc / 1e6))
    print("\nDerated ceiling: %.1f MHz -> %d MHz rounded down" % (cc / 1e6, int(cc // 1e6)))

    print("\nStatic-code holes below the ceiling, every bundle (MHz): %s"
          % "; ".join("%.1f-%.1f" % (a / 1e6, z / 1e6) for a, z in holes(common, 10e6, cc)))

    if "--check" in argv:
        ok = (all(not table[b][2] for b in ("typical", "ss", "fs", "sf")) and table["ff"][2] == [7]
              and (either, n7only, n6only) == (30, 11, 4)
              and int(ceiling(common) // 1e6) == 166)
        print("\n#534 finding %s" % ("re-derives" if ok else "DOES NOT re-derive"))
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
