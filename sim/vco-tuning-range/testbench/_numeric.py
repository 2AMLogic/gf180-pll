"""gf180-pll :: vco-tuning-range :: numeric helpers shared by both analysis paths.

`sim/vco-tuning-range` has two live extraction paths over the same decks: the
manual-invocation scripts (`jitter_extract.py`, `analyze.py`, `analyze_supply.py`,
driven by `run.sh` / `run_supply.sh`) and the `sim/harness`-integrated `derive.py`
/ `derive_supply.py` pair exercised by `sim/tests/test_vco_supply_derive.py`. Both
paths re-implement the same handful of numeric primitives; this module is the one
copy each of `jitter_extract.py`, `derive_supply.py`, `analyze_supply.py`,
`derive.py` and `analyze.py` load, instead of carrying their own.

Neither `testbench/` nor `testbench-supply/` is a Python package, and none of the
affected scripts import each other, so every caller loads this module the same way
`sim/tests/test_vco_supply_derive.py` and `sim/harness/derived.py` already load
sibling modules -- `importlib.util.spec_from_file_location` by path, keyed under a
private name in `sys.modules` so two callers loading it in the same process do not
collide.
"""

from __future__ import annotations


def crossings(t, y, th, tmin):
    """Rising crossings of `th`, linearly interpolated, at times >= tmin."""
    out = []
    for i in range(len(y) - 1):
        if y[i] < th <= y[i + 1] and t[i] >= tmin:
            dy = y[i + 1] - y[i]
            out.append(t[i] if dy == 0 else t[i] + (th - y[i]) * (t[i + 1] - t[i]) / dy)
    return out


def stats(xs):
    """(mean, RMS deviation from the mean, peak-to-peak)."""
    n = len(xs)
    if n == 0:
        return 0.0, 0.0, 0.0
    m = sum(xs) / n
    var = sum((x - m) ** 2 for x in xs) / n
    return m, var**0.5, (max(xs) - min(xs))


def linefit_residual(ts):
    """Residual of crossing times against their least-squares line (TIE)."""
    n = len(ts)
    ks = list(range(n))
    mk = sum(ks) / n
    mt = sum(ts) / n
    sxx = sum((k - mk) ** 2 for k in ks)
    sxy = sum((k - mk) * (t - mt) for k, t in zip(ks, ts))
    slope = sxy / sxx
    return [t - (mt + slope * (k - mk)) for k, t in zip(ks, ts)], slope


def linfit(xs, ys):
    """Least-squares slope/intercept of `ys` against `xs`."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    m = sxy / sxx
    return m, my - m * mx


def mhz(x):
    """A frequency in MHz, formatted the way every record cites it."""
    return "%.4g" % (x / 1e6)


def corner_name(c):
    """A (bundle, temp_c, vdd_v) triple, formatted the way every record cites it."""
    return "%s/%gC/%.2fV" % (c[0], c[1], c[2])
