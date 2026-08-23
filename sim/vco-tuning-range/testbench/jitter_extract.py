#!/usr/bin/env python3
"""gf180-pll :: vco-tuning-range :: period/TIE extraction from tb_vco_supply_jitter.

Reads the `jit.dat` written by the testbench's `.control` block (columns: time,
v(clkq) quiet, v(clks) stepped supply, v(clkr) rippled supply), locates every
rising half-supply crossing by linear interpolation between transient
timepoints, and reduces the three crossing sequences to the jitter metrics the
record reports.

Why crossings and not `.meas`: jitter is a property of the period *sequence*,
and `.meas` reports scalars. Extracting crossings here also lets the quiet
channel act as an explicit numerical-noise floor for the other two.

Metrics, per channel:
  f_mean        (N-1) / (t_last - t_first)
  tj_pp/tj_rms  peak-to-peak and RMS deviation of the individual periods
  c2c_rms       RMS cycle-to-cycle period difference
  tie_pp/rms    deviation of the crossing times from their least-squares line
                (time interval error) -- the quantity a jitter budget consumes

For the stepped channel the sequence is additionally split at `tstepon` into a
pre-step and post-step frequency, giving the *transient* supply-pushing
coefficient, which is not assumed equal to the dc one.

Usage:
  jitter_extract.py <jit.dat> <vsup> <tsettle> <tstepon> <astep> <arip> <frip>
                    <periods-csv-out>
Prints one CSV row (no header) on stdout; writes the full period/TIE sequences
to <periods-csv-out> so a record can commit the sequence as evidence.
"""

import importlib.util
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "_vco_tuning_range_numeric", Path(__file__).resolve().parent / "_numeric.py"
)
_numeric = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_numeric)
crossings = _numeric.crossings
stats = _numeric.stats
linefit_residual = _numeric.linefit_residual
channel_metrics = _numeric.channel_metrics
read_columns = _numeric.read_columns

#: Minimum crossings a channel needs before its statistics mean anything.
MIN_CROSSINGS = 8


def main():
    (dat, vsup, tsettle, tstepon, astep, arip, frip, pout) = sys.argv[1:9]
    vsup, tsettle, tstepon = float(vsup), float(tsettle), float(tstepon)
    astep, arip, frip = float(astep), float(arip), float(frip)

    try:
        t, ys = read_columns(dat)
    except ValueError as exc:
        raise SystemExit("jitter_extract: %s in %s" % (exc, dat))
    if not t:
        raise SystemExit("jitter_extract: no numeric rows in %s" % dat)
    th = vsup / 2.0
    ch = [crossings(t, y, th, tsettle) for y in ys]
    mq, ms, mr = (channel_metrics(c, MIN_CROSSINGS) for c in ch)
    if mq is None or ms is None or mr is None:
        raise SystemExit("jitter_extract: too few crossings (deck window too short)")

    # --- stepped channel: pre/post-step frequency.
    # One period of guard either side keeps the crossing that straddles the
    # step edge out of both estimates.
    guard = ms["period"]
    pre = [x for x in ms["ts"] if x < tstepon - guard]
    post = [x for x in ms["ts"] if x > tstepon + guard]
    if len(pre) < 4 or len(post) < 4:
        raise SystemExit("jitter_extract: step lands outside the measured window")
    f_pre = (len(pre) - 1) / (pre[-1] - pre[0])
    f_post = (len(post) - 1) / (post[-1] - post[0])
    df = f_post - f_pre
    kvdd_tran = df / astep if astep else 0.0
    # Timing error a 1 us open-loop interval accumulates at the post-step
    # frequency offset -- the number a loop-bandwidth budget has to beat.
    tie_1us = 1e-6 * df / f_pre

    # --- rippled channel: measured vs. quasi-static prediction.
    # Excess phase from f(t) = f0 + K*A*sin(2*pi*f_r*t) integrates to a
    # peak-to-peak time error of K*A/(pi*f_r*f0); period modulation is
    # 2*T0*K*A/f0 peak-to-peak.
    if arip and frip:
        tie_pp_pred = abs(kvdd_tran) * arip / (3.14159265358979 * frip * mq["f"])
        tj_pp_pred = 2.0 * (1.0 / mq["f"]) * abs(kvdd_tran) * arip / mq["f"]
    else:
        tie_pp_pred = tj_pp_pred = 0.0

    with open(pout, "w") as fh:
        fh.write("# per-cycle period and TIE sequences, one row per measured cycle\n")
        fh.write("# vsup=%g tsettle=%g tstepon=%g astep=%g arip=%g frip=%g\n"
                 % (vsup, tsettle, tstepon, astep, arip, frip))
        fh.write("cycle,quiet_t_s,quiet_period_s,quiet_tie_s,")
        fh.write("step_t_s,step_period_s,step_tie_s,")
        fh.write("ripple_t_s,ripple_period_s,ripple_tie_s\n")
        n = min(len(mq["per"]), len(ms["per"]), len(mr["per"]))
        for i in range(n):
            fh.write(
                "%d,%.10g,%.6g,%.6g,%.10g,%.6g,%.6g,%.10g,%.6g,%.6g\n"
                % (i, mq["ts"][i], mq["per"][i], mq["tie"][i],
                   ms["ts"][i], ms["per"][i], ms["tie"][i],
                   mr["ts"][i], mr["per"][i], mr["tie"][i])
            )

    sys.stdout.write(
        ",".join(
            "%.6g" % v
            for v in (
                mq["f"], mq["tj_pp"], mq["tj_rms"], mq["c2c_rms"], mq["tie_pp"], mq["tie_rms"],
                f_pre, f_post, df, kvdd_tran, tie_1us,
                mr["f"], mr["tj_pp"], mr["tj_rms"], mr["c2c_rms"], mr["tie_pp"], mr["tie_rms"],
                tie_pp_pred, tj_pp_pred, mq["n"], mr["n"],
            )
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
