"""gf180-pll :: period-jitter :: deterministic period/TIE reduction (#13).

`sim/harness` reports `.measure` scalars. Period jitter is not a scalar
ngspice can measure directly: it is a property of the *sequence* of output
edges, not any single one of them. So the deck writes the locked output
waveform with `wrdata` over the measurement window only, and this module
reduces it -- the shape `sim/harness/README.md` documents for `raw_files` +
`derived`.

The reduction itself is not new: `sim/vco-tuning-range/testbench/_numeric.py`
already carries the crossing-extraction and least-squares-line-residual
primitives every jitter measurement in this repo uses (`jitter_extract.py`,
`derive_supply.py`, and `sim/reference-spur/testbench/derive.py`'s own TIE
cross-check). This module loads that shared file rather than re-implementing
it, exactly the way `derive_supply.py` already does.

Two things this module computes, from one crossing sequence:

``tj_*``   period jitter -- the RMS/peak-to-peak deviation of the per-cycle
           period sequence from its own mean. This is the form
           `spec/pll.md#period-jitter` states its target in (percent of
           period, RMS).
``tie_*``  time interval error -- the RMS/peak-to-peak deviation of the
           crossing times from their own least-squares line. De-trending by
           a fit (rather than assuming a nominal period) keeps a residual
           settling drift from the loop's own release transient out of the
           jitter number, the same reason `sim/reference-spur`'s TIE path
           de-trends by a fit rather than a nominal period.

Everything here is stdlib -- `sim/harness` is stdlib-only by design.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from harness.derived import DerivedTable, fmt_scalar, load_module  # noqa: E402

_numeric = load_module(
    Path(__file__).resolve().parents[2] / "vco-tuning-range" / "testbench" / "_numeric.py"
)
crossings = _numeric.crossings
channel_metrics = _numeric.channel_metrics

#: Minimum crossings before a channel's statistics mean anything -- the same
#: floor `jitter_extract.py` / `derive_supply.py` use.
MIN_CROSSINGS = 8

#: The draft (unratified, #1) period-jitter line this record is read against.
DRAFT_TJ_RMS_PCT = 1.0


def extract_period_jitter(t, y, vdd, tmin):
    """Every period/TIE metric this record reports, from one crossing sequence.

    Pure function of plain sequences (mirrors `derive_supply.extract_jitter`'s
    shape) so `sim/tests/test_period_jitter_derive.py` can replay a synthetic
    waveform of known jitter through it without a simulator.

    Returns ``None`` when the window produced too few crossings to say
    anything -- an early convergence failure or a window too short -- which is
    data (recorded as *not measured*), not an error.
    """
    cross = crossings(t, y, vdd / 2.0, tmin)
    m = channel_metrics(cross, MIN_CROSSINGS)
    if m is None:
        return None
    return {
        "tj_rms_s": m["tj_rms"],
        "tj_pp_s": m["tj_pp"],
        "tj_rms_pct": 100.0 * m["tj_rms"] * m["f"],
        "tj_pp_pct": 100.0 * m["tj_pp"] * m["f"],
        "c2c_rms_s": m["c2c_rms"],
        "tie_rms_s": m["tie_rms"],
        "tie_pp_s": m["tie_pp"],
        "n_cycles": float(m["n"] - 1),
        "f_meas_hz": m["f"],
    }


def derive_point(point):
    """This point's period/TIE jitter, reduced from `clk.dat`.

    The manifest's own `wa` records where the measurement window starts;
    crossings before it (the deck stores from `ktstart`, slightly earlier, so
    the first edge inside the window is not starved of its predecessor) are
    discarded by the `tmin` argument, exactly as `jitter_extract.py` discards
    pre-`tsettle` crossings.
    """
    raw = point.raw("clk.dat")
    if not raw.exists():
        return {}
    rows = raw.rows()
    if len(rows) < 100:
        return {}
    t = raw.column("t")
    clk = raw.column("clk")
    wa = point.get("wa") or float(point.params.get("wa", 0.0))

    out = {}
    out["dt_int_mean"] = (t[-1] - t[0]) / (len(t) - 1)
    metrics = extract_period_jitter(t, clk, point.vdd, wa)
    if metrics:
        for key in (
            "tj_rms_s", "tj_pp_s", "tj_rms_pct", "c2c_rms_s",
            "tie_rms_s", "tie_pp_s", "n_cycles",
        ):
            out[key] = metrics[key]
    return out


def derive_tables(run):
    rows = []
    for pt in run.points:
        pct = pt.get("tj_rms_pct")
        verdict = ""
        if pct is not None:
            verdict = "PASS" if pct <= DRAFT_TJ_RMS_PCT else "FAIL"
        rows.append(
            (
                pt.corner_id,
                pt.corner,
                fmt_scalar(pt.temp_c, "%g"),
                fmt_scalar(pt.vdd, "%.2f"),
                fmt_scalar(pt.get("fout"), "%.6g"),
                fmt_scalar(pt.get("n_cycles"), "%.0f"),
                fmt_scalar(pt.get("tj_rms_s"), "%.4e"),
                fmt_scalar(pct, "%.4f"),
                fmt_scalar(pt.get("tj_pp_s"), "%.4e"),
                fmt_scalar(pt.get("c2c_rms_s"), "%.4e"),
                fmt_scalar(pt.get("tie_rms_s"), "%.4e"),
                fmt_scalar(pt.get("tie_pp_s"), "%.4e"),
                fmt_scalar(pt.get("ferr"), "%.2e"),
                fmt_scalar(pt.get("dn_lvl"), "%.4f"),
                fmt_scalar(pt.get("dt_int_mean"), "%.3e"),
                verdict,
            )
        )
    return [
        DerivedTable(
            name="period_jitter_by_corner",
            description=(
                "deterministic period/TIE jitter of the locked output, measured "
                "directly from the period sequence over the manifest's "
                "measurement window. RANDOM/NOISE-DRIVEN JITTER IS NOT MEASURED "
                "-- see this record's Methodology field."
            ),
            columns=(
                "corner_id", "process", "temp_c", "vdd_v", "fout_hz",
                "n_cycles", "tj_rms_s", "tj_rms_pct", "tj_pp_s", "c2c_rms_s",
                "tie_rms_s", "tie_pp_s", "ferr", "dn_lvl", "dt_int_mean_s",
                "verdict_vs_1pct_rms_draft",
            ),
            rows=tuple(rows),
            notes=(
                "tj_rms_pct is the deterministic (control-ripple-driven) period "
                "jitter as a percentage of the measured output period -- the "
                "form spec/pll.md#period-jitter states its draft <=1.0% RMS "
                "target in. The verdict column is read against that draft, "
                "unratified target (issue #1).",
                "tie_rms_s/tie_pp_s de-trend the crossing sequence by its own "
                "least-squares line before computing RMS/pp, which removes any "
                "residual release-transient settling drift from being counted "
                "as jitter -- the same reason sim/reference-spur's TIE path "
                "de-trends by a fit rather than a nominal period.",
                "This table reports the DETERMINISTIC component only. No "
                "random/noise-driven jitter number appears anywhere in this "
                "record -- see the Methodology field for why.",
            ),
        )
    ]
