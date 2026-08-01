"""cp-compliance (switching bench) reductions.

The per-polarity quantities are measured in the deck's own control block (see
the manifest's `analyses`), because the turn-on/turn-off searches trigger on
`i_ss/2` -- a threshold that only exists once the transient has run.  What is
left for this module is the one derived measurement the pre-migration record
reported but no single `.meas` produced, plus the `cp_switch.csv` table that
record cited.
"""

from harness.derived import DerivedTable


def derive_point(point):
    """`ton_skew` -- the UP-vs-DN turn-on delay difference at this point."""
    ton_up = point.get("ton_up")
    ton_dn = point.get("ton_dn")
    if ton_up is None or ton_dn is None:
        return {}
    return {"ton_skew": ton_up - ton_dn}


def _fmt(value, spec="%.6g"):
    return "" if value is None else spec % value


def derive_tables(run):
    rows = []
    for point in run.points:
        rows.append(
            (
                point.corner,
                f"{point.temp_c:g}",
                f"{point.vdd:.2f}",
                point.params.get("vctrl", ""),
                _fmt(point.get("iup_ss")),
                _fmt(point.get("idn_ss")),
                _fmt(point.get("qup")),
                _fmt(point.get("qdn")),
                _fmt(point.get("wup")),
                _fmt(point.get("wdn")),
                _fmt(point.get("wskew")),
                _fmt(point.get("ton_up")),
                _fmt(point.get("ton_dn")),
                _fmt(point.get("toff_up")),
                _fmt(point.get("toff_dn")),
            )
        )

    return [
        DerivedTable(
            name="cp_switch",
            description=(
                "per (PVT corner, control voltage): steady-state current, delivered "
                "charge, effective pulse width and edge delays for both polarities"
            ),
            notes=(
                "Both polarities driven from the SAME control edge, one instance each, at "
                "the nominal trim code (b1 b0 = 1 0).",
                "iup_ss/idn_ss: steady-state current late in the 5 ns control pulse (A)",
                "qup/qdn: charge delivered over the switching event, including the tail-node "
                "charge-sharing transient (C).  Sign convention: qup > 0 (sourced into the "
                "control node), qdn < 0 (sunk out of it).",
                "wup/wdn: effective pulse width each polarity presents to the loop, q/i_ss (s)",
                "wskew: wup - wdn, the effective UP/DN TIMING mismatch (s) -- the quantity "
                "that turns charge-pump asymmetry into static phase error",
                "ton_*/toff_*: 50%-of-i_ss crossing referenced to the 50% control edge (s)",
            ),
            columns=(
                "process", "temp_c", "vdd_v", "vctrl_v",
                "iup_ss_a", "idn_ss_a", "qup_c", "qdn_c",
                "wup_s", "wdn_s", "wskew_s",
                "ton_up_s", "ton_dn_s", "toff_up_s", "toff_dn_s",
            ),
            rows=tuple(rows),
        )
    ]
