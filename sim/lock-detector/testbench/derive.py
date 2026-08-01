"""lock-detector's reductions: the per-point pass/fail verdict, and the window-edge table.

Ports the awk reductions ``sim/lock-detector/testbench/run.sh`` (pre-harness)
applied per point and per run, verbatim in substance.
"""

from __future__ import annotations

from harness.derived import DerivedTable

_SUFFIX = {
    "f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3,
    "k": 1e3, "meg": 1e6, "g": 1e9, "t": 1e12,
}


def _spice_float(text: str) -> float:
    """Parse a SPICE-style numeric literal ('2.40u', '4.0n', '25e6') to a float."""
    text = text.strip()
    lower = text.lower()
    for suffix in ("meg", "f", "p", "n", "u", "m", "k", "g", "t"):
        if lower.endswith(suffix):
            return float(text[: -len(suffix)]) * _SUFFIX[suffix]
    return float(text)


def _lvl(value, vdd) -> str:
    """A settled digital level: HIGH (>90% rail), LOW (<10%), else CHATTER."""
    if value is None:
        return "?"
    if value > 0.9 * vdd:
        return "HIGH"
    if value < 0.1 * vdd:
        return "LOW"
    return "CHATTER"


def derive_point(point):
    """The four-check acceptance verdict from the pre-harness runner, verbatim.

    A run PASSes only if: deep-in-lock (XB) asserted and stayed HIGH; deep
    -out-of-lock (XC) and frequency-error (XD) stayed LOW; and the perturbed
    copy (XE) asserted before the kick at ktpert and deasserted after it.
    "Before the kick" is tested as assert-time < kick-time rather than as a
    level averaged over the run-up to the kick, because at the slowest
    corners the assert transition itself falls inside any such averaging
    window and would read as CHATTER -- an artefact of the window, not of the
    flag.
    """
    vdd = point.vdd
    il = _lvl(point.get("lb_lvl"), vdd)
    be = _lvl(point.get("lc_lvl"), vdd)
    fe = _lvl(point.get("ld_lvl"), vdd)
    pa = _lvl(point.get("le_lvl"), vdd)

    tb_asrt = point.get("tb_asrt")
    lc_lvl = point.get("lc_lvl")
    te_asrt = point.get("te_asrt")
    te_deas = point.get("te_deas")
    ktpert = point.params.get("ktpert")
    tp = _spice_float(ktpert) if ktpert is not None else None

    ok = (
        il == "HIGH"
        and tb_asrt is not None
        and be == "LOW"
        and lc_lvl is not None
        and fe == "LOW"
        and te_asrt is not None
        and tp is not None
        and te_asrt < tp
        and pa == "LOW"
        and te_deas is not None
    )
    return {"lock_pass": 1.0 if ok else 0.0}


def derive_tables(run):
    """Window edges: per corner, the largest terr that still asserted and the
    smallest that did not -- only for corners the run stepped 3+ distinct
    phase errors at (the window-ladder corners; a grid-only corner has a
    single phase-error point and would contribute a meaningless row).
    """
    seen_terr: dict[tuple, set] = {}
    hi: dict[tuple, float] = {}
    lo: dict[tuple, float] = {}
    for point in run.points:
        key = (point.corner, point.temp_c, point.vdd)
        kterr = point.params.get("kterr")
        if kterr is None:
            continue
        terr = _spice_float(kterr)
        seen_terr.setdefault(key, set()).add(terr)
        level = _lvl(point.get("la_lvl"), point.vdd)
        if level == "HIGH":
            if key not in hi or terr > hi[key]:
                hi[key] = terr
        else:
            if key not in lo or terr < lo[key]:
                lo[key] = terr

    rows = []
    for key in sorted(seen_terr, key=lambda k: (k[0], k[1], k[2])):
        if len(seen_terr[key]) < 3:
            continue
        process, temp_c, vdd = key
        asserted_up_to = f"{hi[key]:.6g}" if key in hi else ""
        did_not_assert_from = f"{lo[key]:.6g}" if key in lo else ""
        rows.append((process, temp_c, vdd, asserted_up_to, did_not_assert_from))

    return [
        DerivedTable(
            name="window_edges",
            description=(
                "per window-ladder corner: the largest swept phase error (terr) that "
                "still left the swept copy (XA) asserted, and the smallest that did "
                "not -- asserted_up_to_s empty means not even the smallest step "
                "asserted, did_not_assert_from_s empty means every step up to the "
                "largest still asserted"
            ),
            columns=("process", "temp_c", "vdd_v", "asserted_up_to_s", "did_not_assert_from_s"),
            rows=tuple(rows),
        )
    ]
