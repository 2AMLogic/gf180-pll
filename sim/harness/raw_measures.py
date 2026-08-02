"""Per-point raw-measurement CSV: the always-on counterpart of derived tables.

``sim/harness`` writes a machine-readable CSV for a testbench's *derived*
tables (see :mod:`derived`) only when its manifest declares
``derived.tables``. The Markdown record always renders a per-point corner
table -- every measurement, every point, PASS/FAIL/ERROR -- but that table
exists only as prose. A testbench that declares no ``derived.tables``
(``sim/divider-ratio-cell``, at the time this module was added) therefore
commits raw ``.log`` files and a Markdown table only: nothing a script can
diff. That is a regression against the pre-harness runner, which always
emitted a per-point CSV.

:func:`write_raw_measures_csv` closes that gap unconditionally: every run
that writes a record also gets ``corners/<record-id>/raw_measures.csv``, one
row per corner point, with the same sweep-axis + measurement + verdict
content the Markdown corner table renders -- and the *identical* verdict
text, via :func:`report.point_verdicts`, so the two artifacts can never
drift apart.

This is a sibling of :mod:`derived`, not an addition to it: a derived table
is campaign-supplied *reduction* over the raw table below, opt-in per
manifest, while this CSV is the raw table itself, always written -- the two
are conceptually distinct evidence, so they get separate writers with the
same append-only contract.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from . import report as report_mod
from .runner import PointResult
from .testbench import Testbench

#: Written into a cell for a declared-optional (or derived) measurement that
#: produced no value at that point. Distinct from an empty cell, which reads
#: as an unexplained gap in the evidence rather than a documented one --
#: "this ladder never tripped" is data, not a missing number.
NOT_MEASURED_LABEL = "not measured"


class RawMeasuresError(RuntimeError):
    """``raw_measures.csv`` already exists -- evidence is append-only."""


def write_raw_measures_csv(
    tb: Testbench, results: list[PointResult], out_dir: Path
) -> Path:
    """Write ``<out_dir>/raw_measures.csv``, one row per corner point.

    Append-only, like :func:`derived.write_derived_tables`: raises rather
    than silently overwriting an existing file (``corners/<record-id>/`` is
    append-only evidence -- see ``sim/README.md``).

    Columns:

    - ``corner``, ``temp_c``, ``vdd`` -- the PVT sweep axes every point has
      (:meth:`PvtPoint.as_dict`).
    - one column per extra sweep axis, for campaigns that sweep beyond PVT
      (:attr:`PvtPoint.axis_points`) -- the union across every point in this
      run, in first-seen order, so a run whose points do not all share the
      same extra axes still gets one column per axis rather than silently
      dropping a point's value.
    - ``corner_id`` -- the ratified ``<process>_<temp>c_<supply>v[_<extra>...]``
      id (``sim/README.md``), matching the ``.log`` filename and the
      Markdown corner table's row key.
    - one column per ``tb.measure_names`` -- every measurement the manifest
      declares, ``.measure`` cards and ``raw_measures``-sourced values alike.
    - ``verdict`` -- PASS / ``FAIL — ...`` / ``ERROR — ...``, identical to
      the Markdown record's corner table (:func:`report.point_verdicts`).

    A point whose ``status`` is not ``"ok"`` (failed to simulate, or its
    derived reduction raised) still gets a row -- an ERROR verdict, not a
    silently dropped point: the whole point is missing evidence, and that is
    itself worth recording. A measurement genuinely absent for a reason other
    than ``not_measured`` (e.g. a required measurement a failed point never
    produced) renders as an empty cell, the same convention
    :func:`derived.write_derived_tables` uses for ``None``.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "raw_measures.csv"
    if path.exists():
        raise RawMeasuresError(
            f"{path} already exists; raw_measures.csv is append-only evidence"
        )

    measure_names = list(tb.measure_names)
    verdicts = report_mod.point_verdicts(tb, results)

    axis_names: list[str] = []
    for result in results:
        for name in result.point.axes:
            if name not in axis_names:
                axis_names.append(name)

    columns = [
        "corner",
        "temp_c",
        "vdd",
        *axis_names,
        "corner_id",
        *measure_names,
        "verdict",
    ]

    buf = io.StringIO(newline="")
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(columns)
    for result in results:
        point = result.point
        axes = point.axes
        not_measured = set(result.not_measured)
        row = [point.corner.name, point.temp_c, point.vdd]
        row += [axes.get(name, "") for name in axis_names]
        row.append(point.corner_id)
        for name in measure_names:
            if name in result.measurements:
                row.append(result.measurements[name])
            elif name in not_measured:
                row.append(NOT_MEASURED_LABEL)
            else:
                row.append("")
        row.append(verdicts.get(point.corner_id, ""))
        writer.writerow(row)
    path.write_text(buf.getvalue())
    return path
