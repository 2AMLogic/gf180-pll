"""Derived metrics: the campaign-supplied reduction over a run's raw table.

The harness reports raw per-point measurements plus min/max/spread. Every real
campaign in this repo reports a *reduction* over those, and it is the
reduction that is the claim:

- a setup/hold ladder is scanned for the smallest passing step (per point);
- a window-edge table is the largest error that still asserted and the
  smallest that did not, per corner, over an extra sweep axis (per run);
- ``retiming_margin.csv`` joins a chain's arrival time against a *different*
  record's per-PVT setup/hold numbers (per run, cross-record).

Those reductions are campaign knowledge, not harness knowledge, so the harness
does not implement them -- it provides the extension point they plug into. A
manifest names a python module next to its ``tb.json``:

    "derived": {
      "module": "derive.py",
      "measures": ["tsetup", "thold"],
      "tables": ["retiming_margin"],
      "joins": {"dff": "divider-ratio/corners/<record-id>/dff_setup_hold.csv"}
    }

and that module may define either or both of:

``derive_point(point) -> dict[str, float]``
    Called once per simulated point, after its measurements are parsed. The
    names it returns must be declared in ``measures``; they then behave
    exactly like measured values (summary, checks, topology groups, the
    record's result table). A declared name the module does not return for a
    given point is recorded as *not measured*, not as an error -- a ladder
    that never tripped legitimately has no value.

``derive_tables(run) -> [DerivedTable, ...]``
    Called once, after every point has run. The names it returns must be
    declared in ``tables``. Each table is written to
    ``corners/<record-id>/<name>.csv`` and rendered into the record.

Both are handed plain, read-only views (:class:`PointView`, :class:`RunView`)
rather than harness internals, so a campaign's reduction cannot accidentally
depend on -- or mutate -- the runner's state.

**Joins** are how the cross-record case is expressed: ``joins`` maps an alias
to a CSV *already written by another record*, path relative to ``sim/``. The
harness parses it (skipping the ``#`` provenance preamble every record CSV in
this repo carries) and hands it to ``derive_tables`` as ``run.joins[alias]``.
``--join alias=path`` supplies or overrides one per invocation, which is what
lets a chain run point at the dff record it is actually being closed against
instead of hardcoding a record-id in a committed manifest.
"""

from __future__ import annotations

import csv
import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path

#: Function names a campaign's derive module may define. Both are optional,
#: but a ``derived`` block that declares ``measures``/``tables`` without the
#: corresponding function is a load error rather than a silently empty column.
POINT_HOOK = "derive_point"
TABLES_HOOK = "derive_tables"


class DerivedError(RuntimeError):
    """A campaign's derive module failed or broke its contract."""


@dataclass(frozen=True)
class DerivedTable:
    """One reduced table, written as CSV and rendered into the record."""

    name: str
    columns: tuple[str, ...]
    rows: tuple[tuple, ...] = ()
    description: str = ""
    notes: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "notes": list(self.notes),
            "columns": list(self.columns),
            "rows": [list(r) for r in self.rows],
        }


@dataclass(frozen=True)
class PointView:
    """Read-only view of one simulated point, handed to ``derive_point``."""

    corner: str
    corner_id: str
    temp_c: float
    vdd: float
    axes: dict[str, str] = field(default_factory=dict)
    params: dict[str, str] = field(default_factory=dict)
    measurements: dict[str, float] = field(default_factory=dict)

    def get(self, name: str, default=None):
        """``measurements[name]``, or ``default`` when the measure did not fire.

        The default default is ``None`` rather than ``0.0`` on purpose: "this
        ``.meas`` did not produce a value" and "it produced zero" are different
        facts, and conflating them is how an expected-failure measurement turns
        into a silently wrong number.
        """
        return self.measurements.get(name, default)


@dataclass(frozen=True)
class JoinTable:
    """A CSV from another record, parsed for a cross-record derived metric."""

    alias: str
    path: Path
    columns: tuple[str, ...]
    rows: tuple[dict[str, str], ...]

    def index_by(self, *columns: str) -> dict[tuple[str, ...], dict[str, str]]:
        """``{(col1, col2, ...): row}`` -- the join key most of these need."""
        missing = [c for c in columns if c not in self.columns]
        if missing:
            raise DerivedError(
                f"join {self.alias!r} ({self.path}) has no column(s) {missing}; "
                f"columns are {list(self.columns)}"
            )
        return {tuple(row[c] for c in columns): row for row in self.rows}


@dataclass(frozen=True)
class RunView:
    """Read-only view of the whole run, handed to ``derive_tables``."""

    experiment: str
    measure_names: tuple[str, ...]
    points: tuple[PointView, ...]
    joins: dict[str, JoinTable] = field(default_factory=dict)

    def join(self, alias: str) -> JoinTable:
        if alias not in self.joins:
            raise DerivedError(
                f"derived metric needs join {alias!r}, which this run did not "
                f"supply; declare it in the manifest's derived.joins or pass "
                f"--join {alias}=<path relative to sim/>"
            )
        return self.joins[alias]


@dataclass
class DerivedSpec:
    """A manifest's ``derived`` block, resolved against the testbench dir."""

    module_path: Path
    measures: tuple[str, ...] = ()
    tables: tuple[str, ...] = ()
    joins: dict[str, str] = field(default_factory=dict)
    _module = None

    def module(self):
        """Import (once) and return the campaign's derive module."""
        if self._module is None:
            self._module = load_module(self.module_path)
        return self._module

    def point_hook(self):
        return getattr(self.module(), POINT_HOOK, None)

    def tables_hook(self):
        return getattr(self.module(), TABLES_HOOK, None)


def load_module(path: Path):
    """Import a campaign's ``derive.py`` by path, without touching sys.path.

    The module name is namespaced by the experiment directory so two campaigns
    may both call their module ``derive.py`` without colliding in
    ``sys.modules``.
    """
    path = Path(path).resolve()
    if not path.is_file():
        raise DerivedError(f"derived module {path} does not exist")
    name = f"_gf180pll_derived_{path.parent.parent.name}_{path.stem}".replace("-", "_")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise DerivedError(f"cannot import derived module {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - surface the campaign's own error
        raise DerivedError(f"derived module {path} failed to import: {exc}") from exc
    return module


def read_join_csv(alias: str, path: Path) -> JoinTable:
    """Parse a record CSV written by this repo's convention.

    Every extracted-metrics CSV under ``sim/*/corners/<record-id>/`` starts
    with a ``#``-commented provenance preamble; the first line that is not a
    comment is the header. Blank lines are ignored, and a trailing comment
    block (some campaigns append notes) is skipped the same way.
    """
    path = Path(path)
    if not path.is_file():
        raise DerivedError(f"join {alias!r}: {path} does not exist")
    lines = [
        line
        for line in path.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not lines:
        raise DerivedError(f"join {alias!r}: {path} has no header row")
    reader = csv.DictReader(lines)
    columns = tuple(reader.fieldnames or ())
    rows = tuple({k: (v or "") for k, v in row.items() if k is not None} for row in reader)
    return JoinTable(alias=alias, path=path, columns=columns, rows=rows)


def derive_point_measures(spec: DerivedSpec, view: PointView) -> dict[str, float]:
    """Run the campaign's per-point reduction, validating what it returns."""
    hook = spec.point_hook()
    if hook is None:
        if spec.measures:
            raise DerivedError(
                f"{spec.module_path} declares derived measures {list(spec.measures)} "
                f"but defines no {POINT_HOOK}() function"
            )
        return {}
    try:
        produced = hook(view) or {}
    except Exception as exc:  # noqa: BLE001 - campaign code, report don't crash
        raise DerivedError(f"{POINT_HOOK}() failed at {view.corner_id}: {exc}") from exc
    if not isinstance(produced, dict):
        raise DerivedError(
            f"{POINT_HOOK}() must return a dict of {{name: value}}, got {type(produced).__name__}"
        )
    declared = set(spec.measures)
    undeclared = sorted(set(produced) - declared)
    if undeclared:
        raise DerivedError(
            f"{POINT_HOOK}() returned undeclared measure(s) {undeclared} at "
            f"{view.corner_id}; add them to the manifest's derived.measures "
            "(a name the record has no column for would be silently dropped)"
        )
    out: dict[str, float] = {}
    for name, value in produced.items():
        if value is None:
            continue  # legitimately not derivable at this point
        try:
            out[name] = float(value)
        except (TypeError, ValueError) as exc:
            raise DerivedError(
                f"{POINT_HOOK}() returned a non-numeric value for {name!r} at "
                f"{view.corner_id}: {value!r}"
            ) from exc
    return out


def derive_run_tables(spec: DerivedSpec, view: RunView) -> list[DerivedTable]:
    """Run the campaign's whole-run reduction, validating what it returns."""
    hook = spec.tables_hook()
    if hook is None:
        if spec.tables:
            raise DerivedError(
                f"{spec.module_path} declares derived tables {list(spec.tables)} "
                f"but defines no {TABLES_HOOK}() function"
            )
        return []
    try:
        produced = hook(view) or []
    except DerivedError:
        raise
    except Exception as exc:  # noqa: BLE001 - campaign code, report don't crash
        raise DerivedError(f"{TABLES_HOOK}() failed: {exc}") from exc
    tables = list(produced.values()) if isinstance(produced, dict) else list(produced)
    for table in tables:
        if not isinstance(table, DerivedTable):
            raise DerivedError(
                f"{TABLES_HOOK}() must return DerivedTable objects, got "
                f"{type(table).__name__}"
            )
    declared = set(spec.tables)
    undeclared = sorted({t.name for t in tables} - declared)
    if undeclared:
        raise DerivedError(
            f"{TABLES_HOOK}() returned undeclared table(s) {undeclared}; add them "
            "to the manifest's derived.tables"
        )
    missing = sorted(declared - {t.name for t in tables})
    if missing:
        raise DerivedError(
            f"{TABLES_HOOK}() did not return declared table(s) {missing}; a record "
            "that silently omits a declared derived table is weaker than the "
            "record it replaces"
        )
    return tables


def write_derived_tables(tables: list[DerivedTable], out_dir: Path) -> list[Path]:
    """Write each derived table as ``<out_dir>/<name>.csv``.

    Append-only, like every other artefact under ``corners/<record-id>/``: an
    existing file is never rewritten.
    """
    written: list[Path] = []
    out_dir.mkdir(parents=True, exist_ok=True)
    for table in tables:
        path = out_dir / f"{table.name}.csv"
        if path.exists():
            raise DerivedError(
                f"{path} already exists; derived tables are append-only evidence"
            )
        lines: list[str] = []
        if table.description:
            lines.append(f"# {table.description}")
        lines += [f"# {note}" for note in table.notes]
        lines.append(",".join(table.columns))
        for row in table.rows:
            lines.append(",".join("" if cell is None else str(cell) for cell in row))
        path.write_text("\n".join(lines) + "\n")
        written.append(path)
    return written
