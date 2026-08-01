"""divider-ratio-dff's reduction: the setup/hold ladder scan.

Ports the awk reduction ``sim/divider-ratio/testbench/run.sh`` (pre-harness)
carried out per point, verbatim in substance: the setup ladder is scanned for
the first step whose clk->Q has degraded more than 10% against the relaxed
(ti = 1.00 ns) reference of the same bank, and the hold ladder is scanned for
the most negative step at which the late data was still not captured. A
ladder step whose ``.measure`` failed (``point.get(...)`` returns ``None``,
because ``tb.json`` marks bank A/B's raw_measures ``optional``) is a violated
step, not a missing one -- that is what makes the scan possible at all.
"""

from __future__ import annotations

from harness.derived import DerivedTable

# Setup ladder, seconds of data-before-clock at the 50% crossings -- must
# stay in step with testbench/tb_dff_setup.sp's ti0..ti9 params.
TI = (1.00e-9, 0.20e-9, 0.10e-9, 0.05e-9, 0.02e-9, 0.00, -0.02e-9, -0.05e-9, -0.10e-9, -0.15e-9)
# Hold ladder, seconds of data-after-clock -- th0..th9.
TH = (0.50e-9, 0.20e-9, 0.10e-9, 0.00, -0.10e-9, -0.20e-9, -0.30e-9, -0.40e-9, -0.50e-9, -0.70e-9)


def _scan_setup_bank(prefix: str, point) -> float:
    """Smallest ladder step whose clk->Q has not degraded >10% vs. step 0."""
    reference = point.get(f"{prefix}0")
    if reference is None:
        # The relaxed (1.00 ns) reference step itself did not capture --
        # every later step is presumably worse, so the whole bank is at its
        # floor.
        return TI[-1]
    result = TI[-1]
    for i in range(1, len(TI)):
        value = point.get(f"{prefix}{i}")
        if value is None or value > 1.1 * reference:
            result = TI[i - 1]
            break
    return result


def _scan_hold(point) -> float:
    """Most negative ladder step at which the late data was still NOT captured."""
    vdd = point.vdd
    result = TH[0]
    for i in range(len(TH)):
        value = point.get(f"hqc{i}")
        if value is not None and value < 0.1 * vdd:
            result = TH[i]
    return result


def derive_point(point):
    tsetup_a = _scan_setup_bank("cqa", point)
    tsetup_b = _scan_setup_bank("cqb", point)
    out = {"tsetup_s": max(tsetup_a, tsetup_b), "thold_s": _scan_hold(point)}
    tcq_r = point.get("cqa0")
    if tcq_r is not None:
        out["tcq_r_s"] = tcq_r
    tcq_f = point.get("cqb0")
    if tcq_f is not None:
        out["tcq_f_s"] = tcq_f
    return out


def derive_tables(run):
    """The per-corner table sim/divider-ratio-chain's retiming_margin.csv joins.

    Written so a downstream campaign can close its own retiming budget against
    this record without hardcoding a record-id in a committed manifest --
    ``--join dff=divider-ratio-dff/corners/<this-record-id>/dff_setup_hold.csv``.
    """
    rows = []
    for point in run.points:
        tsetup = point.get("tsetup_s")
        thold = point.get("thold_s")
        if tsetup is None or thold is None:
            continue
        rows.append(
            (
                point.corner,
                f"{point.temp_c:g}",
                f"{point.vdd:.2f}",
                f"{tsetup:.6g}",
                f"{thold:.6g}",
                f"{point.get('tcq_r_s', float('nan')):.6g}",
                f"{point.get('tcq_f_s', float('nan')):.6g}",
            )
        )
    return [
        DerivedTable(
            name="dff_setup_hold",
            description=(
                "tsetup_s/thold_s per PVT point, from the setup/hold ladder scan "
                "above -- the join input sim/divider-ratio-chain's retiming_margin.csv "
                "needs to close the retiming flop's setup budget"
            ),
            columns=("process", "temp_c", "vdd_v", "tsetup_s", "thold_s", "tcq_r_s", "tcq_f_s"),
            rows=tuple(rows),
        )
    ]
