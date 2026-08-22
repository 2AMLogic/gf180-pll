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

**Raw files** are the same idea pointed at a point's *own* output. A whole
class of claim here is a *sequence*, not a scalar: a per-cycle period sequence
(jitter / TIE), a decimated I-V curve. ``.measure`` cannot report one, so the
deck writes it itself with ``wrdata`` and the campaign reduces it. The
manifest's top-level ``raw_files`` key declares those filenames (see
``testbench.RawFileSpec``); the harness runs each point in its own scratch
directory, captures what the deck wrote there, and hands it over as a
:class:`RawFile` -- path plus lazily-parsed numeric columns -- on
``point.raw_files`` / ``point.raw(name)``, reachable from both hooks
(``run.points[i].raw(...)`` in ``derive_tables``). A file the deck never wrote
arrives as a :class:`RawFile` whose ``exists()`` is ``False`` and whose
``rows()`` is empty, so the reduction returns nothing for that point and the
measure is recorded as not-measured -- exactly what a reduction that finds
nothing to reduce already does.
"""

from __future__ import annotations

import csv
import importlib.util
import io
import sys
import threading
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
class RawFile:
    """One file a point's own deck wrote, handed to a campaign's reduction.

    This is the raw-waveform counterpart of :class:`JoinTable`: where a join is
    a CSV *another record* already wrote, a raw file is what *this* point's
    deck emitted during its own simulation (``wrdata jit.dat v(clkq) ...``).

    The file is not parsed until something asks for :meth:`rows` -- a full
    transient dump is megabytes, and a reduction that only wants
    :attr:`path` (to hand to its own reader) must not pay for parsing it.
    Once parsed, the result is cached for the life of the view.

    A declared file the deck never wrote is **not** an error: it arrives here
    with ``exists()`` false and ``rows()`` empty, so a reduction that finds
    nothing to reduce returns nothing and its measure is recorded as
    not-measured. That is the same treatment a ladder that never tripped gets.
    """

    #: The filename as the manifest (and the deck's ``wrdata`` line) spells it.
    name: str
    #: Where the harness left it: the point's scratch directory, or the
    #: retained copy under ``corners/<record-id>/`` for a ``retain`` file.
    path: Path
    #: Manifest-declared column names, in the order the deck writes them.
    #: Empty when the manifest did not name them -- index by position instead.
    columns: tuple[str, ...] = ()
    _cache: dict = field(
        default_factory=dict, repr=False, compare=False, hash=False
    )

    def exists(self) -> bool:
        """Did the deck actually write this file at this point?"""
        return self.path.is_file()

    def text(self) -> str:
        """The file verbatim, or ``""`` when the deck never wrote it."""
        return self.path.read_text() if self.exists() else ""

    def rows(self) -> tuple[tuple[float, ...], ...]:
        """Every numeric row, parsed from ``wrdata``'s whitespace columns.

        ``wrdata`` writes one whitespace-separated row of floats per print
        step and no header. Blank lines, and a leading comment or header line
        (``#``/``*``, or a first line that is not numeric), are skipped. A
        *later* non-numeric line, or a row whose width does not match the
        first, is a hard error rather than a silently dropped sample: that
        means the file is truncated or has ngspice's own error text spliced
        into it, and silently reducing over the surviving rows would report a
        number the waveform does not support.
        """
        if "rows" not in self._cache:
            self._cache["rows"] = self._parse()
        return self._cache["rows"]

    def column(self, key) -> tuple[float, ...]:
        """One column, by manifest-declared name or by 0-based position."""
        rows = self.rows()
        index = self._column_index(key)
        if rows and index >= len(rows[0]):
            raise DerivedError(
                f"raw file {self.name!r} ({self.path}) has {len(rows[0])} column(s); "
                f"no column at index {index}"
                + (f" (declared columns: {list(self.columns)})" if self.columns else "")
            )
        return tuple(row[index] for row in rows)

    def _column_index(self, key) -> int:
        if isinstance(key, int):
            return key
        if key in self.columns:
            return self.columns.index(key)
        raise DerivedError(
            f"raw file {self.name!r} has no column named {key!r}; declared columns "
            f"are {list(self.columns)}"
            + (
                " -- name them in the manifest's raw_files[...].columns, or index "
                "by position"
                if not self.columns
                else ""
            )
        )

    def _parse(self) -> tuple[tuple[float, ...], ...]:
        if not self.exists():
            return ()
        rows: list[tuple[float, ...]] = []
        width: int | None = None
        for lineno, line in enumerate(self.path.read_text().splitlines(), start=1):
            fields = line.split()
            if not fields:
                continue
            if fields[0].startswith(("#", "*")):
                continue
            try:
                values = tuple(float(f) for f in fields)
            except ValueError:
                if not rows:
                    continue  # a header line the deck (or a tool) prepended
                raise DerivedError(
                    f"raw file {self.name!r} ({self.path}) line {lineno} is not a "
                    f"row of numbers: {line.strip()!r}"
                ) from None
            if width is None:
                width = len(values)
            elif len(values) != width:
                raise DerivedError(
                    f"raw file {self.name!r} ({self.path}) line {lineno} has "
                    f"{len(values)} column(s), but the file started with {width} -- "
                    "the file is truncated or interleaved"
                )
            rows.append(values)
        return tuple(rows)


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
    #: Files this point's own deck wrote, keyed by the manifest's ``raw_files``
    #: filename. Present for every declared file, whether or not the deck
    #: actually wrote it -- see :class:`RawFile`.
    raw_files: dict[str, RawFile] = field(default_factory=dict)

    def get(self, name: str, default=None):
        """``measurements[name]``, or ``default`` when the measure did not fire.

        The default default is ``None`` rather than ``0.0`` on purpose: "this
        ``.meas`` did not produce a value" and "it produced zero" are different
        facts, and conflating them is how an expected-failure measurement turns
        into a silently wrong number.
        """
        return self.measurements.get(name, default)

    def raw(self, name: str) -> RawFile:
        """The declared raw file ``name``, for this point.

        Undeclared is an error (like an undeclared join): the manifest has to
        say which files the deck writes, or the harness cannot isolate them per
        point or decide whether they are evidence. *Unwritten* is not an
        error -- check :meth:`RawFile.exists`.
        """
        if name not in self.raw_files:
            raise DerivedError(
                f"derived metric needs raw file {name!r} at {self.corner_id}, which "
                f"this testbench does not declare; add it to the manifest's top-level "
                f"raw_files (declared: {sorted(self.raw_files)})"
            )
        return self.raw_files[name]


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
    #: Guards the check-then-set below. ``run_grid()`` dispatches PVT points
    #: across a ``ThreadPoolExecutor`` (whenever ``jobs > 1``), and every point
    #: shares the same ``DerivedSpec`` instance (the manifest is loaded once
    #: and passed by reference), so multiple worker threads can call
    #: ``module()`` on it concurrently. One lock per instance -- not a
    #: module-level lock -- keeps the common (already-imported) path free of
    #: cross-campaign contention.
    _module_lock: threading.Lock = field(
        default_factory=threading.Lock, repr=False, compare=False
    )

    def module(self):
        """Import (once) and return the campaign's derive module.

        Double-checked locking: the fast path (module already imported) never
        pays for lock acquisition. Only the first caller(s) to observe
        ``_module is None`` contend for the lock, and only one of them
        actually imports -- whichever loses the race re-checks
        ``_module is None`` inside the lock and finds it already set.
        """
        if self._module is None:
            with self._module_lock:
                if self._module is None:
                    self._module = load_module(self.module_path)
        return self._module

    def point_hook(self):
        return getattr(self.module(), POINT_HOOK, None)

    def tables_hook(self):
        return getattr(self.module(), TABLES_HOOK, None)


def fmt_scalar(value, spec: str = "%.6g") -> str:
    """Format one scalar for a derived table cell, ``""`` when not measured.

    Shared by campaign ``derive.py`` modules that build ``DerivedTable`` rows
    from ``PointView``/``RunView`` values -- ``None`` (not measured) and a
    real value are different facts (see :meth:`PointView.get`), so this keeps
    that distinction all the way into the rendered cell instead of coercing a
    missing measurement into ``"0"`` or an empty numeric format error.
    """
    return "" if value is None else spec % value


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

    Header and cells are written through :mod:`csv`, so a cell that contains a
    comma (``ss/-40C, B5, Vctrl 2.1 V``) is quoted instead of silently
    splitting into extra columns. A reduction's cells are *prose* -- worst
    corner citations, check text -- so commas in them are normal, not exotic.
    Quoting matters more here than in a throwaway report: these files are
    append-only evidence, the record's Markdown cites them by name as the full
    table behind a truncated one, and this repo's own tests read committed
    evidence with :class:`csv.DictReader`. A row whose column count disagrees
    with its header is a corrupt artefact that can only be repaired by
    re-minting the whole record.
    """
    written: list[Path] = []
    out_dir.mkdir(parents=True, exist_ok=True)
    for table in tables:
        path = out_dir / f"{table.name}.csv"
        if path.exists():
            raise DerivedError(
                f"{path} already exists; derived tables are append-only evidence"
            )
        buf = io.StringIO(newline="")
        if table.description:
            buf.write(f"# {table.description}\n")
        for note in table.notes:
            buf.write(f"# {note}\n")
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(list(table.columns))
        for row in table.rows:
            writer.writerow(["" if cell is None else str(cell) for cell in row])
        path.write_text(buf.getvalue())
        written.append(path)
    return written
