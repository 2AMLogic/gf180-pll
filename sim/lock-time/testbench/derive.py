"""lock-time's per-point verdict reductions, ported from ``run.sh``.

``tb.json`` limits are static numbers applied to one measurement at a time.
Two of the legacy runner's row decisions are not expressible that way, so they
are derived per point here and the manifest checks the derived values:

``lock_pass``
    ``run.sh`` initializes a row to FAIL and accepts it only after a LOCK
    rising edge was measured *and* LOCK was high (>= 1.5 V) at the end of the
    window.  ``1.0`` when both hold, ``0.0`` otherwise -- a missing edge is a
    FAIL, never a silent pass, while the other measurements of the row are
    kept as they are.

``dn_guard``
    The PFD DN-branch integration guard, against the supply-relative floor
    ``ACC_DN_FRAC * VDD`` of *this* point (not one fixed floor for the grid).
    Three dispositions, as in ``run.sh``::

        2  PASS     dn_lvl >= ACC_DN_FRAC * VDD
        1  SUSPECT  dn_lvl below the floor on a row that is not a lock PASS
        0  FAIL     dn_lvl below the floor on a row that IS a lock PASS

    The raw ``dn_lvl`` stays a measurement of its own.  The manifest requires
    ``dn_guard >= 2``, so SUSPECT and FAIL both fail the row; the code keeps
    them distinguishable.  A point without ``dn_lvl`` is an error at the
    harness level (the measure is required), never coerced to a disposition.
"""

from __future__ import annotations

#: run.sh's ACC_DN_FRAC: the DN floor as a fraction of the point's supply.
ACC_DN_FRAC = 3e-4
#: run.sh's lock-held threshold on ``lock_at_end`` [V].
LOCK_HELD_V = 1.5

DN_PASS = 2.0
DN_SUSPECT = 1.0
DN_FAIL = 0.0


def lock_pass(point) -> float:
    """``1.0`` iff a LOCK rising edge was measured and LOCK ended high."""
    rise = point.get("t_lock_last_rise")
    end = point.get("lock_at_end")
    if rise is None or end is None:
        return 0.0
    return 1.0 if end >= LOCK_HELD_V else 0.0


def dn_guard(point, locked: float):
    """The three-valued DN guard code, or ``None`` when ``dn_lvl`` is absent."""
    dn = point.get("dn_lvl")
    if dn is None:
        return None
    if dn >= ACC_DN_FRAC * point.vdd:
        return DN_PASS
    return DN_FAIL if locked == 1.0 else DN_SUSPECT


def derive_point(point):
    locked = lock_pass(point)
    return {"lock_pass": locked, "dn_guard": dn_guard(point, locked)}
