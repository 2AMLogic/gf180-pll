"""gf180-pll :: vco-tuning-range :: numeric helpers shared by both analysis paths.

`sim/vco-tuning-range` has two live extraction paths over the same decks: the
manual-invocation scripts (`jitter_extract.py`, `analyze.py`, `analyze_supply.py`,
driven by `run.sh` / `run_supply.sh`) and the `sim/harness`-integrated `derive.py`
/ `derive_supply.py` pair exercised by `sim/tests/test_vco_supply_derive.py`. The
numeric primitives those paths share repo-wide -- the rising-crossing extraction
and the least-squares line fit -- live in `sim/harness/numeric.py` (#985), the
one package every extractor imports; this module keeps the vco-tuning-range
statistics built on top of them and is what the path-loading callers load.

Neither `testbench/` nor `testbench-supply/` is a Python package, and none of the
affected scripts import each other, so every caller loads this module the same way
`sim/tests/test_vco_supply_derive.py` and `sim/harness/derived.py` already load
sibling modules -- `importlib.util.spec_from_file_location` by path, keyed under a
private name in `sys.modules` so two callers loading it in the same process do not
collide.
"""

from __future__ import annotations

import csv
import sys as _sys
from pathlib import Path as _Path

# `harness.numeric` holds the shared primitives this module re-exported since
# #985; this file is itself loaded by path (its directory is not a package),
# so it puts `sim/` on `sys.path` the way its loading scripts do, guarded so
# repeated loads under different private names add nothing.
_SIM = _Path(__file__).resolve().parents[2]
if str(_SIM) not in _sys.path:
    _sys.path.insert(0, str(_SIM))

from harness.numeric import crossings, linfit  # noqa: E402,F401 -- re-exported

__all__ = [
    "crossings", "linfit", "stats", "linefit_residual", "mhz", "ts",
    "channel_metrics", "corner_name", "corner_temp_name", "read_csv_rows",
    "read_columns", "local_kvco",
]


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


def mhz(x):
    """A frequency in MHz, formatted the way every record cites it."""
    return "%.4g" % (x / 1e6)


def ts(x):
    """A time in the unit a reader can compare at a glance (as the record does)."""
    return "%.3g ns" % (x * 1e9) if abs(x) >= 1e-9 else "%.3g ps" % (x * 1e12)


def channel_metrics(ts, min_crossings=8):
    """One channel's period / TIE statistics, or None if too few crossings."""
    if len(ts) < min_crossings:
        return None
    per = [ts[i + 1] - ts[i] for i in range(len(ts) - 1)]
    pm, prms, ppp = stats(per)
    c2c = [per[i + 1] - per[i] for i in range(len(per) - 1)]
    _, c2crms, _ = stats(c2c)
    tie, slope = linefit_residual(ts)
    _, tierms, tiepp = stats(tie)
    return {
        "n": len(ts),
        "f": (len(ts) - 1) / (ts[-1] - ts[0]),
        "period": pm,
        "tj_rms": prms,
        "tj_pp": ppp,
        "c2c_rms": c2crms,
        "tie_rms": tierms,
        "tie_pp": tiepp,
        "slope": slope,
        "tie": tie,
        "per": per,
        "ts": ts,
    }


def corner_name(c):
    """A (bundle, temp_c, vdd_v) triple, formatted the way every record cites it."""
    return "%s/%gC/%.2fV" % (c[0], c[1], c[2])


def corner_temp_name(bundle, temp_c, vdd=None):
    """A (bundle, temp_c[, vdd]) grouping key, formatted the way every supply
    record cites it -- vdd is optional because some groupings are per-temp
    only."""
    out = "%s/%gC" % (bundle, float(temp_c))
    return out if vdd is None else out + "/%.2fV" % float(vdd)


def read_csv_rows(path):
    """Rows of a `run.sh`-written CSV, skipping its leading `#`-comment lines."""
    return list(csv.DictReader(l for l in open(path) if not l.startswith("#")))


def read_columns(path):
    """``(t, [y1, y2, y3])`` from one point's `jit.dat`, tolerating both layouts.

    `wrdata` writes ``t y1 t y2 t y3`` by default and ``t y1 y2 y3`` under
    ``set wr_singlescale``; this accepts either, since a deck edited to drop
    that line would otherwise silently mis-column.

    Skips non-numeric lines, then (defensively) any row whose length
    disagrees with the first numeric row's. Returns ``((), ())`` if the file
    has no numeric rows at all, and raises ``ValueError`` if the surviving
    column count is neither 4 nor 6 -- callers translate both edge cases into
    their own exit/error style.
    """
    rows = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line[0] not in "-+.0123456789":
                continue
            try:
                rows.append([float(x) for x in line.split()])
            except ValueError:
                continue
    if not rows:
        return (), ()
    ncol = len(rows[0])
    cols = [[r[i] for r in rows if len(r) == ncol] for i in range(ncol)]
    if ncol == 4:  # `set wr_singlescale`: t, y1, y2, y3
        return cols[0], cols[1:]
    if ncol == 6:  # default wrdata: (t,y1),(t,y2),(t,y3)
        return cols[0], [cols[1], cols[3], cols[5]]
    raise ValueError("unexpected column count %d" % ncol)


def local_kvco(vs, fs):
    """Central-difference dF/dV at each sweep point (one-sided at the ends)."""
    k = []
    for i in range(len(vs)):
        if i == 0:
            k.append((fs[1] - fs[0]) / (vs[1] - vs[0]))
        elif i == len(vs) - 1:
            k.append((fs[-1] - fs[-2]) / (vs[-1] - vs[-2]))
        else:
            k.append((fs[i + 1] - fs[i - 1]) / (vs[i + 1] - vs[i - 1]))
    return k
