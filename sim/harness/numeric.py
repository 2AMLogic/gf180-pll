"""gf180-pll :: harness :: the numeric primitives every ``sim/`` extractor shares.

One copy of the two primitives that had grown acknowledged duplicates across
``sim/`` extractors (#985): the rising threshold crossing linearly interpolated
between the two stored samples that straddle it, and the least-squares line
fit.  ``sim/harness`` is the one package every extractor already imports, so it
is the one home they get; the per-campaign copies these replace are deleted.

Every former copy is reproduced EXACTLY, including its boundary behaviour --
``sim/`` results are append-only evidence, so a refactor here must leave every
recorded derived table byte-identical:

=========================  ================================  ===============
former copy                kept pairs                        extras
=========================  ================================  ===============
``_numeric.crossings``     earlier sample ``>= tmin``        --
(vco-tuning-range)
``rb_extract.rising_crossings``  (no gate)                   --
(random-bound)
``derive.rising_crossings``  later sample inside ``[t0, t1]``  --
(reference-spur)
``ib_extract.crossings_with_slew``  (no gate)                chord slew
(in-band-bound)
``ib_extract.falling_crossings_with_slew``  falling edges    chord slew
(in-band-bound)
=========================  ================================  ===============

Two edge differences between the copies were confirmed rather than assumed
before unifying:

- **The zero-slope guards were dead code.**  The vco-tuning-range copy's
  ``t[i] if dy == 0 else ...`` and the reference-spur copy's ``dy <= 0``
  continue are unreachable: the strict straddle test ``y[i-1] < level <= y[i]``
  already implies ``dy > 0``.  They are dropped here.
- **The two windowing conventions gate different samples of the straddling
  pair, so they stay two arguments instead of merging.**  ``tmin`` drops a
  pair whose EARLIER sample precedes it (the settle window of the
  vco-tuning-range jitter extractors); ``window`` keeps a pair whose LATER
  sample lies inside it (the reference-spur TIE window).  A merged convention
  would move the first kept crossing whenever a window boundary falls between
  two stored samples -- exactly the silent change this consolidation must not
  make.

Everything here is stdlib -- ``sim/harness`` is stdlib-only by design.
"""

from __future__ import annotations


def crossings(t, y, level, tmin=None, window=None, slew=False, falling=False):
    """Rising (or falling) crossings of ``level``, placed on the chord between
    the two stored timepoints that straddle it.

    A pair ``(t[i-1], t[i])`` straddles the level, rising, when
    ``y[i-1] < level <= y[i]``; falling when ``y[i-1] >= level > y[i]`` (each
    the mirror of the other, strict on one side so a sample sitting exactly on
    the level belongs to the crossing that leaves it, and a flat segment at
    the level produces no crossing).  The crossing time is the linear
    interpolation between the pair -- at a fine timestep ceiling the chord's
    error is the clean copy's period spread, which the period-jitter runs
    report beside their noisy copies as the numerical floor.

    ``tmin`` drops any pair whose earlier sample precedes it -- the
    settle-window convention of ``sim/vco-tuning-range``'s jitter extractors,
    where the first edge inside the window must not be starved of its
    predecessor sample.  ``window`` is an inclusive ``(t0, t1)`` keeping pairs
    whose LATER sample lies inside it -- ``sim/reference-spur``'s TIE window.
    The two conventions are deliberately not merged; see the module docstring.

    ``slew=True`` additionally requires ``t[i] > t[i-1]`` (a chord slew rate
    needs increasing time) and returns one ``{"t": ..., "slew": ...}`` dict per
    crossing instead of the bare time, with the chord's own slope -- positive
    for both directions.  A chord UNDER-estimates the instantaneous slope of a
    convex edge, so ``1/SR`` from it is an over-estimate: the safe direction
    for an edge-jitter bound.

    ``falling=True`` selects falling crossings (used with ``slew`` by
    ``sim/period-jitter/in-band-bound``, whose charge-pump overlap window
    pairs each rising crossing with the next falling one).
    """
    out = []
    for i in range(1, len(t)):
        a, b = y[i - 1], y[i]
        if falling:
            hit = a >= level > b
            dlevel = a - level
            dy = a - b
        else:
            hit = a < level <= b
            dlevel = level - a
            dy = b - a
        if not hit:
            continue
        if tmin is not None and t[i - 1] < tmin:
            continue
        if window is not None and not window[0] <= t[i] <= window[1]:
            continue
        if slew and not t[i] > t[i - 1]:
            continue
        tc = t[i - 1] + dlevel * (t[i] - t[i - 1]) / dy
        if slew:
            out.append({"t": tc, "slew": dy / (t[i] - t[i - 1])})
        else:
            out.append(tc)
    return out


def linfit(xs, ys):
    """Least-squares ``(slope, intercept, r2)`` of ``ys`` against ``xs``.

    Returns ``(None, None, None)`` when there are fewer than two points or
    ``xs`` has no spread -- a fit those inputs cannot define -- and ``r2 = 1``
    when ``ys`` has no spread (every point already on a horizontal line).
    """
    m = len(xs)
    if m < 2:
        return None, None, None
    mx = sum(xs) / m
    my = sum(ys) / m
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0:
        return None, None, None
    sxy = sum((xs[i] - mx) * (ys[i] - my) for i in range(m))
    slope = sxy / sxx
    intercept = my - slope * mx
    syy = sum((y - my) ** 2 for y in ys)
    r2 = (sxy * sxy) / (sxx * syy) if syy > 0 else 1.0
    return slope, intercept, r2
