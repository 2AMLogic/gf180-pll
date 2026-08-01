"""Testbench manifests.

Testbenches follow the directory convention ratified in ``sim/README.md``:
each experiment gets ``sim/<experiment-slug>/`` and its testbench lives in
that experiment's ``testbench/`` subdirectory:

    sim/<experiment-slug>/testbench/tb.json            the manifest (this module)
    sim/<experiment-slug>/testbench/<something>.spice  a *netlist fragment*

The fragment must NOT contain ``.include`` of models, ``.lib``, ``.temp``,
``.control``, ``.endc``, ``.end``, or ``.measure``/``.meas``: the harness owns
all of those so that one netlist can be swept across the whole PVT grid
without editing, and so a corner-varying measurement can never be silently
pinned by a fragment author. The harness hands the fragment these parameters:

    vdd_val   the supply for this PVT point (nominal, +tol or -tol)
    vdd_nom   the nominal supply, for ratio-style measurements
    temp_c    the temperature for this PVT point (also set via .temp)

plus anything in the manifest's ``params`` map.

Two measurement mechanisms, because a bare post-analysis ``let`` expression
(bandgap's only form) cannot express a triggered delay measurement:

    measure       {name: <let-expression>}, evaluated after the analyses run
                  (e.g. "v(out)", "-i(vdd)") -- good for op-point reads.
    raw_measures  {name: {"analysis": "tran", "expr": "trig ... targ ..."}},
                  rendered as a literal ``.measure <analysis> <name> <expr>``
                  statement -- needed for trig/targ, when/rise, avg/from-to,
                  and anything else ngspice's own .measure syntax supports.
                  This is what most of this repo's real campaigns (delay
                  chains, lock time, jitter) actually need.

An optional third key, ``topology_groups``, exists purely for the *record*:
a campaign whose deck carries several sub-circuits (a delay-cell deck with
unstarved rings, starved rings, an inverter chain and bare devices) would
otherwise render as one 27-column table with no hint of which measurement
belongs to which topology. Declaring the grouping lets the renderer emit one
sub-table per topology instead. It changes nothing about how the deck is
composed, run, parsed or checked -- omit it and every campaign behaves
exactly as before.

Six further optional keys exist for campaigns the single fixed ``params``
map cannot express. Every one of them defaults to off, so a manifest that
does not use them behaves exactly as it did before they existed:

    dut        repo-root-relative netlist(s) composed ahead of the fragment,
               so a committed ``design/netlist/<block>.spice`` export can be
               the DUT without being pasted into the fragment (where it would
               silently go stale).
    dut_export ``{"top": "<block>"}`` -- the *per-record* counterpart of
               ``dut``, for a block ``design/netlist.sh`` deliberately does
               NOT commit (currently just ``pfd_cp``; see that script's own
               header comment for why). The harness runs
               ``design/netlist.sh --top <block> <scratch-dir>`` itself and
               composes the result exactly where a ``dut`` entry would go --
               nothing under ``testbench/`` becomes a generated artefact, and
               there is still only one committed-adjacent copy of the export:
               the frozen ``netlist-snapshots/<record-id>.spice`` a record
               actually cites. A manifest may declare ``dut`` or
               ``dut_export``, not both.
    sweeps     extra independent axes beyond the PVT grid, each point
               carrying its own derived deck parameters.
    grid       the union of blocks a run actually covers, when the extra-axis
               cross-product is deliberately *not* run in full.
    raw_files  files a point's own deck writes during simulation (``wrdata``),
               declared so the harness can isolate them per point, hand them
               to the campaign's reduction, and -- when the file itself is the
               evidence -- retain them under ``corners/<record-id>/``.
    derived    the campaign's own reduction over the per-point table (see
               ``sim/harness/derived.py``).

and one per-measurement flag, ``optional``, for the case where a **failed**
``.measure`` is the pass condition ("this must never assert"): an absent
optional result is recorded as not-measured data instead of failing the point
and discarding its successful measurements.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path

from .corners import (
    DEFAULT_CORNER_SET,
    DEFAULT_NOMINAL_SUPPLY_V,
    DEFAULT_SUPPLY_TOLERANCE,
    DEFAULT_TEMPERATURES_C,
    SUPPLY_ALIASES,
    GridBlock,
    SweepAxis,
    SweepPoint,
)
from .derived import DerivedSpec

MANIFEST_NAME = "tb.json"

#: ``sim/`` -- ``dut`` paths are resolved relative to the repository root so a
#: manifest names the committed export exactly as the repo spells it.
REPO_ROOT = Path(__file__).resolve().parents[2]

#: Name of the per-experiment subdirectory that holds the testbench, per
#: the directory convention in ``sim/README.md``.
TESTBENCH_DIRNAME = "testbench"

FORBIDDEN_DIRECTIVES = (
    ".control", ".endc", ".end", ".lib", ".temp", ".include", ".measure", ".meas",
)

#: Name of the synthetic group that collects measurements a manifest's
#: ``topology_groups`` did not assign to any topology. Reserved: a manifest
#: may not declare a group by this name.
UNGROUPED_TOPOLOGY = "ungrouped"

#: Keys a ``topology_groups`` entry may carry in its object form. Anything
#: else is a typo (``measure`` for ``measures`` being the obvious one) and is
#: rejected rather than silently ignored.
TOPOLOGY_GROUP_KEYS = ("measures", "description")

#: Keys a ``dut_export`` block may carry.
DUT_EXPORT_KEYS = ("top",)
#: Keys a ``sweeps`` axis may carry.
SWEEP_AXIS_KEYS = ("points", "description")
#: Keys one point on a ``sweeps`` axis may carry.
SWEEP_POINT_KEYS = ("params", "description")
#: Keys a ``grid`` block may carry.
GRID_BLOCK_KEYS = ("description", "corners", "temperatures_c", "supplies", "axes")
#: Keys the ``derived`` block may carry.
DERIVED_KEYS = ("module", "measures", "tables", "joins")
#: Keys a ``raw_files`` entry may carry.
RAW_FILE_KEYS = ("description", "columns", "retain")
#: Filename suffixes this repo's ``.gitignore`` swallows tree-wide (scratch
#: ngspice output). A ``retain``ed raw file may not use one: it would be copied
#: into the evidence tree under ``corners/<record-id>/`` and then never be
#: committed -- an evidence-looking path holding a still-scratch file, which is
#: strictly worse than not retaining it at all.
UNCOMMITTABLE_RAW_SUFFIXES = (".raw", ".log")
#: Characters a sweep-point id may use. ``_`` is excluded because it is the
#: unambiguous field separator in ``sim/README.md``'s corner-id grammar, and a
#: point id becomes one of those fields.
SWEEP_ID_EXTRA_CHARS = "-.+"


@dataclass
class RawMeasure:
    analysis: str
    expr: str
    #: A failed ``.measure`` for this name is data, not an error. See the
    #: module docstring: for a lock detector's "must never assert" copies the
    #: absent result *is* the pass condition.
    optional: bool = False


@dataclass(frozen=True)
class RawFileSpec:
    """One file a point's own deck writes, declared in ``raw_files``.

    ``.measure`` reports scalars. A whole class of this repo's claims is a
    *sequence* instead -- a per-cycle period sequence (jitter/TIE), a decimated
    I-V curve -- which the deck emits with ``wrdata <name> <vectors...>`` from
    its ``.control`` block and a campaign reduces itself. Declaring the file
    here is what lets the harness:

    - run each point in its **own** scratch directory, so concurrent points
      (``-j``) cannot overwrite one another's identically-named output;
    - hand the file to ``derive_point()`` / ``derive_tables()`` as a
      :class:`~harness.derived.RawFile` (path plus parsed columns) instead of
      leaving the reduction to guess where the runner put it;
    - retain it as committed evidence when -- and only when -- the manifest
      says the file itself is the evidence (``retain``).

    ``columns`` is optional and purely a readability aid: it names the columns
    the deck's ``wrdata`` line writes, in order, so a reduction can say
    ``raw.column("clkq")`` rather than ``raw.column(2)``. It is NOT validated
    against the file (the harness cannot know what the deck wrote); a width
    mismatch surfaces when the reduction asks for a column that is not there.
    """

    name: str
    columns: tuple[str, ...] = ()
    description: str = ""
    #: ``False`` (the default) keeps the file in the run's git-ignored scratch
    #: tree. ``True`` copies it into ``corners/<record-id>/<corner-id>-<name>``
    #: -- append-only committed evidence, on the same terms as the sibling
    #: ``<corner-id>.log``. Off by default because a full transient dump is
    #: megabytes per point and is *input* to the claim, not the claim; turn it
    #: on for the decimated/derived artefact a record actually cites.
    retain: bool = False


@dataclass
class TopologyGroup:
    """One sub-circuit / topology's slice of a testbench's measurements.

    Only the *record* consumes this: the deck, the sweep and the checks are
    all indifferent to grouping.
    """

    name: str
    measures: tuple[str, ...]
    description: str = ""


def _check_forbidden_directives(source: Path, kind: str) -> None:
    """Reject a fragment or DUT netlist that owns what the harness owns.

    Shared by :func:`validate_netlist` (committed ``dut`` and the fragment,
    checked at ``load()`` time) and :meth:`DutExportSpec.resolve` (a
    ``dut_export``, checked the moment it materializes -- which is later than
    ``load()``, since it does not exist yet at parse time). Same rule, same
    message, in both places: a ``.lib``/``.temp`` that leaked into either kind
    of DUT netlist would pin every corner of every campaign that names it.
    """
    problems: list[str] = []
    for lineno, raw in enumerate(source.read_text().splitlines(), start=1):
        line = raw.strip().lower()
        if not line.startswith("."):
            continue
        directive = line.split()[0]
        if directive in FORBIDDEN_DIRECTIVES:
            problems.append(f"  line {lineno}: {raw.strip()}")
    if problems:
        raise ValueError(
            f"{source}: {kind} must not contain "
            f"{', '.join(FORBIDDEN_DIRECTIVES)} -- the harness supplies the models, "
            "corner libs, temperature, measurements and the control block:\n"
            + "\n".join(problems)
        )


@dataclass
class DutExportSpec:
    """A manifest's ``dut_export`` block -- a per-record (non-committed) DUT.

    ``design/netlist.sh`` keeps two export conventions (see its own header
    comment): a COMMITTED one (``dut`` composes those) and a PER-RECORD one,
    currently just ``pfd_cp``, which is exported fresh on every invocation and
    deliberately has no committed file under ``design/netlist/`` for a
    manifest to name -- committing one would be a second source of truth
    beside the per-record ``netlist-snapshots/<record-id>.spice`` freeze
    ``sim/README.md`` already mandates.

    So this spec does not *name* a path the way ``dut`` does -- it names a
    ``--top`` value, and resolving it (:meth:`resolve`) actually runs
    ``design/netlist.sh --top <top> <outdir>`` into a scratch directory under
    ``sim/<slug>/work/`` (the existing, already-gitignored convention every
    ``sim/lib/simenv.sh`` campaign's ``run.sh`` uses for the same export).

    Resolution is deferred to first use, not done in ``load()``/``testbench.
    load()`` itself: ``sim/harness/README.md`` already promises the ``derived``
    module "is imported lazily (never during ``--list``)", for the same
    reason -- parsing or listing a manifest must never shell out to xschem.
    ``resolve()`` is the only call site that can trigger the export; every
    consumer of the composed DUT goes through :attr:`Testbench.resolved_dut`,
    which calls it.

    ``resolve()`` is idempotent and thread-safe (double-checked locking, the
    same pattern ``derived.DerivedSpec.module()`` uses -- see #76): every PVT
    point ``run_grid()`` dispatches (across a ``ThreadPoolExecutor`` whenever
    ``jobs > 1``) shares this one instance, so the first point to reach
    ``compose_deck()`` pays for the one xschem invocation the run needs, and
    every other point -- including ones racing it concurrently -- gets back
    the same cached, already-validated path.
    """

    top: str
    outdir: Path
    _path: Path | None = field(default=None, init=False, repr=False, compare=False)
    _lock: threading.Lock = field(
        default_factory=threading.Lock, init=False, repr=False, compare=False
    )

    def resolve(self) -> Path:
        if self._path is None:
            with self._lock:
                if self._path is None:
                    self._path = self._export()
        return self._path

    def _export(self) -> Path:
        netlist_sh = REPO_ROOT / "design" / "netlist.sh"
        if not netlist_sh.is_file():
            raise FileNotFoundError(
                f"dut_export: {netlist_sh} does not exist -- cannot export top "
                f"{self.top!r}"
            )
        self.outdir.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(
            [str(netlist_sh), "--top", self.top, str(self.outdir)],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"dut_export: 'design/netlist.sh --top {self.top} {self.outdir}' "
                f"failed (exit {proc.returncode}):\n{proc.stdout}{proc.stderr}"
            )
        exported = self.outdir / "dut.spice"
        if not exported.is_file():
            raise FileNotFoundError(
                f"dut_export: design/netlist.sh --top {self.top} did not produce "
                f"{exported}"
            )
        # Checked here, not at load() time: the file does not exist until this
        # runs, so this is the earliest point the same rule a committed `dut`
        # is held to (see _check_forbidden_directives) can be applied to it.
        _check_forbidden_directives(exported, "dut netlists")
        return exported


@dataclass
class Testbench:
    directory: Path
    name: str
    netlist: Path
    description: str = ""
    claim: str = ""
    methodology: tuple[str, ...] = ()
    nominal_supply_v: float = DEFAULT_NOMINAL_SUPPLY_V
    supply_tolerance: float = DEFAULT_SUPPLY_TOLERANCE
    temperatures_c: tuple[float, ...] = DEFAULT_TEMPERATURES_C
    corners: tuple[str, ...] = (DEFAULT_CORNER_SET,)
    extra_lib_sections: tuple[str, ...] = ()
    analyses: tuple[str, ...] = ("op",)
    measure: dict[str, str] = field(default_factory=dict)
    raw_measures: dict[str, RawMeasure] = field(default_factory=dict)
    topology_groups: tuple[TopologyGroup, ...] = ()
    params: dict[str, str | float] = field(default_factory=dict)
    checks: dict[str, dict] = field(default_factory=dict)
    options: tuple[str, ...] = ()
    dut: tuple[Path, ...] = ()
    dut_export: DutExportSpec | None = None
    sweeps: tuple[SweepAxis, ...] = ()
    grid_blocks: tuple[GridBlock, ...] = ()
    optional_measures: frozenset[str] = frozenset()
    raw_files: tuple[RawFileSpec, ...] = ()
    derived: DerivedSpec | None = None

    @property
    def raw_file_names(self) -> list[str]:
        """Filenames the deck is declared to write, in manifest order."""
        return [spec.name for spec in self.raw_files]

    @property
    def experiment(self) -> str:
        """The ``<experiment-slug>`` this testbench belongs to.

        ``sim/<experiment-slug>/testbench/tb.json`` -> ``<experiment-slug>``.
        """
        return self.directory.parent.name

    @property
    def experiment_dir(self) -> Path:
        """``sim/<experiment-slug>/`` -- where records/corners/snapshots live."""
        return self.directory.parent

    @property
    def simulated_measure_names(self) -> list[str]:
        """Names ngspice itself produces: ``measure`` then ``raw_measures``."""
        return list(self.measure) + list(self.raw_measures)

    @property
    def derived_measure_names(self) -> list[str]:
        """Names the campaign's ``derive_point()`` contributes, in manifest order."""
        return list(self.derived.measures) if self.derived else []

    @property
    def measure_names(self) -> list[str]:
        """Every measurement name -- simulated first, then derived, in order."""
        return self.simulated_measure_names + self.derived_measure_names

    @property
    def required_measure_names(self) -> list[str]:
        """Simulated measurements whose absence really is a failed point.

        Derived measures are never in this set: a reduction that finds nothing
        to reduce (a ladder that never tripped) has legitimately produced no
        value, and is recorded as not-measured for the same reason an
        ``optional`` ``.measure`` is.
        """
        return [n for n in self.simulated_measure_names if n not in self.optional_measures]

    def is_optional(self, name: str) -> bool:
        """Is an absent value for ``name`` data rather than an error?"""
        return name in self.optional_measures or name in self.derived_measure_names

    @property
    def measure_groups(self) -> tuple[TopologyGroup, ...]:
        """The topology grouping the record should render, or ``()``.

        Empty when the manifest declares no ``topology_groups`` -- that is the
        signal to the renderer to keep the single flat table single-topology
        testbenches have always produced.

        When groups *are* declared, any measurement no group claimed is
        collected into a trailing :data:`UNGROUPED_TOPOLOGY` group, so a
        partially-grouped manifest still renders every measurement rather than
        silently dropping the ones nobody assigned.
        """
        if not self.topology_groups:
            return ()
        claimed = {name for group in self.topology_groups for name in group.measures}
        leftover = tuple(name for name in self.measure_names if name not in claimed)
        groups = tuple(self.topology_groups)
        if leftover:
            groups += (
                TopologyGroup(
                    name=UNGROUPED_TOPOLOGY,
                    measures=leftover,
                    description=(
                        "measurements this manifest's topology_groups did not assign"
                    ),
                ),
            )
        return groups

    @property
    def netlist_sha256(self) -> str:
        return hashlib.sha256(self.netlist.read_bytes()).hexdigest()

    @property
    def manifest_sha256(self) -> str:
        return hashlib.sha256((self.directory / MANIFEST_NAME).read_bytes()).hexdigest()

    @property
    def resolved_dut(self) -> tuple[Path, ...]:
        """``dut`` plus the resolved ``dut_export``, in that order.

        This is the ONLY place ``dut_export`` is actually resolved (see
        :meth:`DutExportSpec.resolve`) -- every consumer that needs the
        composed DUT (the generated deck, the frozen snapshot, provenance)
        goes through here rather than touching ``dut_export`` directly, so
        there is exactly one call site that can trigger the export.
        ``load()`` itself never calls this, which is what keeps parsing (and
        ``--list``) from shelling out to xschem.
        """
        if self.dut_export is None:
            return self.dut
        return self.dut + (self.dut_export.resolve(),)

    @property
    def netlist_sources(self) -> tuple[Path, ...]:
        """Every file the DUT deck is made of: DUT sources, then the fragment.

        DUT first, because the exports define the subcircuits the fragment
        instantiates -- the same order ``sim/lib/assemble_closed_loop.sh``
        concatenates them in. Resolves ``dut_export`` (via
        :attr:`resolved_dut`) on first access.
        """
        return self.resolved_dut + (self.netlist,)

    def compose_netlist(self) -> str:
        """The self-contained DUT + stimulus text, for the frozen snapshot.

        The generated *deck* ``.include``s these files rather than inlining
        them (so a failing corner can be re-run by hand against the live
        sources); the *snapshot* inlines them, so the frozen artefact a record
        cites is self-contained even after ``design/netlist.sh`` re-exports.
        """
        chunks: list[str] = []
        for source in self.netlist_sources:
            rel = _repo_relative(source)
            chunks.append(
                f"* ---- {rel} (sha256 {hashlib.sha256(source.read_bytes()).hexdigest()})\n"
                + source.read_text().rstrip("\n")
                + "\n"
            )
        return "\n".join(chunks)

    @property
    def composed_sha256(self) -> str:
        return hashlib.sha256(self.compose_netlist().encode()).hexdigest()

    def provenance(self) -> dict:
        record = {
            "name": self.name,
            "description": self.description,
            "claim": self.claim,
            "experiment": self.experiment,
            "directory": self.directory.name,
            "netlist": self.netlist.name,
            "netlist_sha256": self.netlist_sha256,
            "manifest_sha256": self.manifest_sha256,
            "nominal_supply_v": self.nominal_supply_v,
            "supply_tolerance": self.supply_tolerance,
        }
        dut_sources = self.resolved_dut
        if dut_sources:
            record["dut"] = [
                {
                    "path": _repo_relative(p),
                    "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                }
                for p in dut_sources
            ]
            record["composed_sha256"] = self.composed_sha256
        return record


def _repo_relative(path: Path) -> str:
    """``path`` spelled the way the repo spells it, or absolutely if outside."""
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _require(manifest: dict, key: str, path: Path):
    if key not in manifest:
        raise ValueError(f"{path}: missing required key {key!r}")
    return manifest[key]


def _optional_flag(spec: dict, path: Path, where: str) -> bool:
    value = spec.get("optional", False)
    if not isinstance(value, bool):
        raise ValueError(f"{path}: {where}.optional must be true or false, got {value!r}")
    return value


def _load_measures(manifest: dict, path: Path) -> tuple[dict[str, str], set[str]]:
    """Parse ``measure``: either ``name: "<expr>"`` or ``name: {expr, optional}``.

    The object form exists only so a ``let``-expression measurement can carry
    the same ``optional`` flag a ``raw_measures`` entry can. The bare-string
    form is unchanged and remains the normal spelling.
    """
    measures: dict[str, str] = {}
    optional: set[str] = set()
    for name, spec in manifest.get("measure", {}).items():
        if isinstance(spec, str):
            measures[name] = spec
            continue
        if not isinstance(spec, dict) or "expr" not in spec:
            raise ValueError(
                f"{path}: measure[{name!r}] must be a let-expression string, or an "
                'object with an \'expr\' key (e.g. {"expr": "v(out)", "optional": true})'
            )
        unknown = sorted(set(spec) - {"expr", "optional"})
        if unknown:
            raise ValueError(
                f"{path}: measure[{name!r}] has unknown key(s) {unknown}; "
                "supported keys are ['expr', 'optional']"
            )
        measures[name] = spec["expr"]
        if _optional_flag(spec, path, f"measure[{name!r}]"):
            optional.add(name)
    return measures, optional


def _load_raw_measures(manifest: dict, path: Path) -> tuple[dict[str, RawMeasure], set[str]]:
    raw: dict[str, RawMeasure] = {}
    optional: set[str] = set()
    for name, spec in manifest.get("raw_measures", {}).items():
        if not isinstance(spec, dict) or "expr" not in spec:
            raise ValueError(
                f"{path}: raw_measures[{name!r}] must be an object with at least "
                "an 'expr' key (e.g. {\"analysis\": \"tran\", \"expr\": \"trig ... targ ...\"})"
            )
        unknown = sorted(set(spec) - {"analysis", "expr", "optional"})
        if unknown:
            raise ValueError(
                f"{path}: raw_measures[{name!r}] has unknown key(s) {unknown}; "
                "supported keys are ['analysis', 'expr', 'optional']"
            )
        is_optional = _optional_flag(spec, path, f"raw_measures[{name!r}]")
        raw[name] = RawMeasure(
            analysis=spec.get("analysis", "tran"), expr=spec["expr"], optional=is_optional
        )
        if is_optional:
            optional.add(name)
    return raw, optional


def _load_dut(manifest: dict, path: Path) -> tuple[Path, ...]:
    """Parse ``dut``: repo-root-relative netlist(s) composed ahead of the fragment.

    This is the answer to "how does a committed ``design/netlist/<block>.spice``
    export become the DUT without being pasted into the committed fragment".
    The export stays where ``design/netlist.sh`` writes it; the manifest names
    it; the harness composes and freezes the pair. Nothing under
    ``testbench/`` becomes a generated artefact that can go stale.
    """
    raw = manifest.get("dut")
    if raw is None:
        return ()
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list) or not raw or not all(isinstance(p, str) for p in raw):
        raise ValueError(
            f"{path}: 'dut' must be a repo-root-relative netlist path or a list of them "
            '(e.g. ["design/netlist/div23_cell.spice"])'
        )
    resolved: list[Path] = []
    for entry in raw:
        candidate = Path(entry)
        if not candidate.is_absolute():
            candidate = REPO_ROOT / entry
        if not candidate.is_file():
            raise FileNotFoundError(
                f"{path}: dut netlist {entry!r} does not exist (looked at {candidate}). "
                "Run design/netlist.sh to export it from the schematic."
            )
        resolved.append(candidate)
    return tuple(resolved)


def _load_dut_export(
    manifest: dict, path: Path, directory: Path
) -> DutExportSpec | None:
    """Parse ``dut_export``: a per-record (non-committed) DUT, by ``--top`` name.

    This is the per-record counterpart of ``dut`` -- see the module docstring
    and :class:`DutExportSpec`. Unlike ``dut``, nothing is resolved here:
    ``design/netlist.sh`` is not run until :attr:`Testbench.resolved_dut` is
    first accessed, well after ``load()`` returns.
    """
    raw = manifest.get("dut_export")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError(
            f"{path}: 'dut_export' must be an object, e.g. {{\"top\": \"pfd_cp\"}}"
        )
    unknown = sorted(set(raw) - set(DUT_EXPORT_KEYS))
    if unknown:
        raise ValueError(
            f"{path}: dut_export has unknown key(s) {unknown}; supported keys "
            f"are {list(DUT_EXPORT_KEYS)}"
        )
    top = raw.get("top")
    if not isinstance(top, str) or not top:
        raise ValueError(
            f"{path}: dut_export.top must name a design/netlist.sh --top value, "
            'e.g. "pfd_cp"'
        )
    if manifest.get("dut") is not None:
        raise ValueError(
            f"{path}: a manifest may declare 'dut' (committed convention) or "
            "'dut_export' (per-record convention), not both -- see "
            "design/netlist.sh's two export conventions"
        )
    # sim/<slug>/work/dut-export/<top>/ -- scratch, already covered by the
    # existing 'sim/*/work/' gitignore rule every sim/lib/simenv.sh campaign's
    # WORK dir already relies on. Namespaced by <top> so a future manifest
    # naming a second per-record top cannot collide with this one's export.
    outdir = directory.parent / "work" / "dut-export" / top
    return DutExportSpec(top=top, outdir=outdir)


def _sweep_id_ok(value: str) -> bool:
    return bool(value) and all(
        ch.isalnum() or ch in SWEEP_ID_EXTRA_CHARS for ch in value
    )


def _load_sweeps(manifest: dict, path: Path) -> tuple[SweepAxis, ...]:
    """Parse the optional ``sweeps`` key -- extra axes beyond the PVT grid.

    ::

        "sweeps": {
          "rate": {
            "description": "input rate",
            "points": {
              "f200": {"params": {"kf": "200e6", "ktstep": "2e-11"}},
              "f010": {"params": {"kf": "10e6",  "ktstep": "4e-10"}}
            }
          }
        }

    Each point's id is written out in full rather than derived from a value,
    because the id becomes a field of the corner-id and ``sim/README.md`` fixes
    that field's spelling (``<name><value>``, no separator, the value exactly
    as the deck spells it). Deriving it would silently rename evidence.
    """
    raw = manifest.get("sweeps")
    if raw is None:
        return ()
    if not isinstance(raw, dict) or not raw:
        raise ValueError(
            f"{path}: 'sweeps' must be a non-empty object mapping an axis name to "
            "an object with a 'points' map"
        )
    axes: list[SweepAxis] = []
    for name, spec in raw.items():
        if not name or not isinstance(name, str):
            raise ValueError(f"{path}: sweeps keys must be non-empty strings")
        if not isinstance(spec, dict):
            raise ValueError(f"{path}: sweeps[{name!r}] must be an object")
        unknown = sorted(set(spec) - set(SWEEP_AXIS_KEYS))
        if unknown:
            raise ValueError(
                f"{path}: sweeps[{name!r}] has unknown key(s) {unknown}; "
                f"supported keys are {list(SWEEP_AXIS_KEYS)}"
            )
        points_spec = spec.get("points")
        if not isinstance(points_spec, dict) or not points_spec:
            raise ValueError(
                f"{path}: sweeps[{name!r}] must have a non-empty 'points' object "
                "mapping a point id to its parameters"
            )
        points: list[SweepPoint] = []
        for point_id, point_spec in points_spec.items():
            if not _sweep_id_ok(point_id):
                raise ValueError(
                    f"{path}: sweeps[{name!r}] point id {point_id!r} must be non-empty "
                    f"and use only alphanumerics and {list(SWEEP_ID_EXTRA_CHARS)} -- it "
                    "becomes a '_'-separated field of the corner-id (sim/README.md)"
                )
            if not isinstance(point_spec, dict):
                raise ValueError(
                    f"{path}: sweeps[{name!r}][{point_id!r}] must be an object with a "
                    "'params' map"
                )
            unknown = sorted(set(point_spec) - set(SWEEP_POINT_KEYS))
            if unknown:
                raise ValueError(
                    f"{path}: sweeps[{name!r}][{point_id!r}] has unknown key(s) "
                    f"{unknown}; supported keys are {list(SWEEP_POINT_KEYS)}"
                )
            params = point_spec.get("params", {})
            if not isinstance(params, dict):
                raise ValueError(
                    f"{path}: sweeps[{name!r}][{point_id!r}].params must be an object"
                )
            points.append(
                SweepPoint(
                    axis=name,
                    id=point_id,
                    params=tuple((k, str(v)) for k, v in params.items()),
                    description=point_spec.get("description", ""),
                )
            )
        axes.append(
            SweepAxis(
                name=name,
                points=tuple(points),
                description=spec.get("description", ""),
            )
        )
    return tuple(axes)


def _load_grid_blocks(
    manifest: dict, path: Path, axes: tuple[SweepAxis, ...]
) -> tuple[GridBlock, ...]:
    """Parse the optional ``grid`` key -- the union of slices a run covers.

    Every block must carry a ``description``. That is the structural half of
    ``sim/README.md``'s "every swept variable must be named, with its points,
    in the record's corner-matrix field": a thinned axis cannot be declared
    without simultaneously writing down why, and the renderer copies those
    descriptions into the record verbatim.
    """
    raw = manifest.get("grid")
    if raw is None:
        return ()
    if not isinstance(raw, list) or not raw:
        raise ValueError(
            f"{path}: 'grid' must be a non-empty list of blocks, each with a "
            "'description' saying why that slice is run"
        )
    if not axes:
        raise ValueError(
            f"{path}: 'grid' only means something alongside 'sweeps' -- without an "
            "extra axis the PVT grid is already fully described by 'corners', "
            "'temperatures_c' and 'supply_tolerance'"
        )
    known_axes = {a.name: a for a in axes}
    blocks: list[GridBlock] = []
    seen: set[str] = set()
    for index, spec in enumerate(raw):
        if not isinstance(spec, dict):
            raise ValueError(f"{path}: grid[{index}] must be an object")
        unknown = sorted(set(spec) - set(GRID_BLOCK_KEYS))
        if unknown:
            raise ValueError(
                f"{path}: grid[{index}] has unknown key(s) {unknown}; supported keys "
                f"are {list(GRID_BLOCK_KEYS)}"
            )
        description = spec.get("description", "")
        if not isinstance(description, str) or not description.strip():
            raise ValueError(
                f"{path}: grid[{index}] must have a non-empty 'description' -- a "
                "deliberately thinned grid is only evidence if the record says why"
            )
        if description in seen:
            raise ValueError(
                f"{path}: grid[{index}] repeats the description {description!r}; each "
                "block's description identifies it in the record, so they must differ"
            )
        seen.add(description)
        block_corners = tuple(spec.get("corners", ()) or ())
        block_temps = tuple(float(t) for t in spec.get("temperatures_c", ()) or ())
        supplies_raw = spec.get("supplies", ()) or ()
        supplies: list[float | str] = []
        for entry in supplies_raw:
            if isinstance(entry, str):
                if entry not in SUPPLY_ALIASES:
                    raise ValueError(
                        f"{path}: grid[{index}].supplies has unknown alias {entry!r}; "
                        f"use a number or one of {list(SUPPLY_ALIASES)}"
                    )
                supplies.append(entry)
            else:
                supplies.append(float(entry))
        axes_spec = spec.get("axes", {}) or {}
        if not isinstance(axes_spec, dict):
            raise ValueError(
                f"{path}: grid[{index}].axes must be an object mapping an axis name "
                "to the list of point ids this block runs"
            )
        block_axes: list[tuple[str, tuple[str, ...]]] = []
        for axis_name, ids in axes_spec.items():
            if axis_name not in known_axes:
                raise ValueError(
                    f"{path}: grid[{index}].axes names axis {axis_name!r}, which is not "
                    f"declared in 'sweeps' ({', '.join(known_axes)})"
                )
            if not isinstance(ids, list) or not ids:
                raise ValueError(
                    f"{path}: grid[{index}].axes[{axis_name!r}] must be a non-empty "
                    "list of point ids"
                )
            missing = [i for i in ids if i not in known_axes[axis_name].ids]
            if missing:
                raise ValueError(
                    f"{path}: grid[{index}].axes[{axis_name!r}] names point(s) {missing} "
                    f"that axis {axis_name!r} does not declare "
                    f"({', '.join(known_axes[axis_name].ids)})"
                )
            block_axes.append((axis_name, tuple(ids)))
        blocks.append(
            GridBlock(
                description=description,
                corners=block_corners,
                temperatures_c=block_temps,
                supplies=tuple(supplies),
                axes=tuple(block_axes),
            )
        )
    return tuple(blocks)


def _load_raw_files(manifest: dict, path: Path) -> tuple[RawFileSpec, ...]:
    """Parse the optional ``raw_files`` key -- what a point's own deck writes.

    Two accepted spellings, matching ``topology_groups``' precedent -- a bare
    list of filenames, or an object carrying per-file options::

        "raw_files": ["jit.dat"]

        "raw_files": {
          "jit.dat": {
            "description": "three buffered VCO outputs, one row per print step",
            "columns": ["t", "clkq", "clks", "clkr"],
            "retain": false
          }
        }

    The key is the filename **exactly as the deck's ``wrdata`` line spells
    it**, and it is that same string a reduction looks the file up by. It must
    be a plain filename: a path separator, ``..`` or an absolute path is
    rejected, because the harness's per-point isolation guarantee only holds
    for files the deck writes into its own working directory.
    """
    raw = manifest.get("raw_files")
    if raw is None:
        return ()
    if isinstance(raw, str):
        raise ValueError(
            f"{path}: 'raw_files' must be a list of filenames or an object mapping "
            f'a filename to its options, not a bare string (use ["{raw}"])'
        )
    if isinstance(raw, list):
        entries = {name: {} for name in raw}
        if len(entries) != len(raw):
            raise ValueError(f"{path}: 'raw_files' lists the same filename twice")
    elif isinstance(raw, dict):
        entries = raw
    else:
        raise ValueError(
            f"{path}: 'raw_files' must be a list of filenames or an object mapping "
            "a filename to its options"
        )
    if not entries:
        raise ValueError(
            f"{path}: 'raw_files' is empty -- omit the key entirely rather than "
            "declaring a capture the deck does not do"
        )

    specs: list[RawFileSpec] = []
    for name, spec in entries.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{path}: raw_files keys must be non-empty filenames")
        if name != Path(name).name or name in (".", "..") or Path(name).is_absolute():
            raise ValueError(
                f"{path}: raw_files[{name!r}] must be a plain filename with no "
                "directory part -- the harness runs each point in its own scratch "
                "directory and captures what the deck wrote there"
            )
        if not isinstance(spec, dict):
            raise ValueError(
                f"{path}: raw_files[{name!r}] must be an object of options "
                '(e.g. {"columns": ["t", "vout"], "retain": true})'
            )
        unknown = sorted(set(spec) - set(RAW_FILE_KEYS))
        if unknown:
            raise ValueError(
                f"{path}: raw_files[{name!r}] has unknown key(s) {unknown}; "
                f"supported keys are {list(RAW_FILE_KEYS)}"
            )
        columns = spec.get("columns", ()) or ()
        if isinstance(columns, str) or not isinstance(columns, (list, tuple)):
            raise ValueError(
                f"{path}: raw_files[{name!r}].columns must be a list of column names, "
                "in the order the deck's wrdata line writes them"
            )
        columns = tuple(columns)
        if not all(isinstance(c, str) and c.strip() for c in columns):
            raise ValueError(
                f"{path}: raw_files[{name!r}].columns entries must be non-empty names"
            )
        if len(set(columns)) != len(columns):
            raise ValueError(
                f"{path}: raw_files[{name!r}].columns repeats a name; a reduction "
                "looks a column up by name, so they must be distinct"
            )
        description = spec.get("description", "")
        if not isinstance(description, str):
            raise ValueError(
                f"{path}: raw_files[{name!r}].description must be a string"
            )
        retain = spec.get("retain", False)
        if not isinstance(retain, bool):
            raise ValueError(
                f"{path}: raw_files[{name!r}].retain must be true or false, got "
                f"{retain!r}"
            )
        if retain and Path(name).suffix.lower() in UNCOMMITTABLE_RAW_SUFFIXES:
            raise ValueError(
                f"{path}: raw_files[{name!r}] cannot be retained under that name -- "
                f"this repo's .gitignore drops {', '.join(UNCOMMITTABLE_RAW_SUFFIXES)} "
                "tree-wide, so the copy would sit in corners/<record-id>/ looking "
                "like evidence and never be committed. Write it as .dat/.csv, or "
                "leave retain off."
            )
        specs.append(
            RawFileSpec(
                name=name, columns=columns, description=description, retain=retain
            )
        )
    return tuple(specs)


def _load_derived(
    manifest: dict, path: Path, directory: Path, known: list[str]
) -> DerivedSpec | None:
    """Parse the optional ``derived`` key -- the campaign's own reduction."""
    raw = manifest.get("derived")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError(
            f"{path}: 'derived' must be an object with a 'module' key naming a python "
            "file next to this manifest"
        )
    unknown = sorted(set(raw) - set(DERIVED_KEYS))
    if unknown:
        raise ValueError(
            f"{path}: derived has unknown key(s) {unknown}; supported keys are "
            f"{list(DERIVED_KEYS)}"
        )
    module = raw.get("module")
    if not isinstance(module, str) or not module:
        raise ValueError(f"{path}: derived.module must name a python file, e.g. 'derive.py'")
    module_path = (directory / module).resolve()
    try:
        module_path.relative_to(directory.resolve())
    except ValueError:
        raise ValueError(
            f"{path}: derived.module {module!r} must live inside this testbench "
            "directory -- a reduction is part of the testbench, and the snapshot "
            "has to be able to name it"
        ) from None
    if not module_path.is_file():
        raise FileNotFoundError(f"{path}: derived.module {module_path} does not exist")

    measures = tuple(raw.get("measures", ()) or ())
    tables = tuple(raw.get("tables", ()) or ())
    for name in measures:
        if not name.replace("_", "").isalnum():
            raise ValueError(
                f"{path}: derived measure name {name!r} must be alphanumeric/underscore"
            )
        if name in known:
            raise ValueError(
                f"{path}: derived measure {name!r} collides with a simulated "
                "measurement of the same name"
            )
    if len(set(measures)) != len(measures) or len(set(tables)) != len(tables):
        raise ValueError(f"{path}: derived.measures / derived.tables must not repeat a name")
    for name in tables:
        if not name.replace("_", "").replace("-", "").isalnum():
            raise ValueError(
                f"{path}: derived table name {name!r} must be alphanumeric with "
                "'_'/'-' (it becomes corners/<record-id>/<name>.csv)"
            )
    joins = raw.get("joins", {}) or {}
    if not isinstance(joins, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in joins.items()
    ):
        raise ValueError(
            f"{path}: derived.joins must map an alias to a sim/-relative CSV path"
        )
    if not measures and not tables:
        raise ValueError(
            f"{path}: derived must declare at least one of 'measures' or 'tables' -- "
            "an undeclared reduction would produce a column or file the record "
            "cannot describe"
        )
    return DerivedSpec(
        module_path=module_path,
        measures=measures,
        tables=tables,
        joins=dict(joins),
    )


def _load_extra_lib_sections(manifest: dict, path: Path) -> tuple[str, ...]:
    """Parse the optional ``extra_lib_sections`` key.

    A *corner* is a bundle of model ``.lib`` sections, one per device family
    (see ``corners.py``). A handful of gf180mcu model sections belong to no
    family axis at all and are therefore in no bundle -- ``cap_mim``, the
    legacy-name MIM subcircuits of ``sm141064.ngspice``, is the case this
    exists for: nothing pulls it in, so a deck that instantiates
    ``cap_mim_1f0fF`` cannot resolve that name under any corner.

    These sections are corner-INDEPENDENT by construction: they are added
    unconditionally, at every PVT point, after the corner's own sections, so
    they cannot silently pin a corner-varying axis the way a ``.lib`` inside
    a netlist fragment would. Anything that *does* vary by corner belongs in
    ``corners.py`` as a bundle, not here.
    """
    raw = manifest.get("extra_lib_sections")
    if raw is None:
        return ()
    if isinstance(raw, str) or not isinstance(raw, (list, tuple)):
        raise ValueError(
            f"{path}: 'extra_lib_sections' must be a list of model .lib section names"
        )
    sections: list[str] = []
    for section in raw:
        if not isinstance(section, str) or not section.strip():
            raise ValueError(
                f"{path}: extra_lib_sections entries must be non-empty section names"
            )
        if section not in sections:
            sections.append(section)
    return tuple(sections)


def _load_topology_groups(
    manifest: dict, path: Path, known: list[str]
) -> tuple[TopologyGroup, ...]:
    """Parse the optional ``topology_groups`` key.

    Two accepted spellings per group -- a bare list of measurement names, or
    an object carrying that list plus a one-line ``description`` rendered as
    the sub-table's caption::

        "topology_groups": {
          "ring1x": ["r1_fosc", "r1_tstage"],
          "ring4x": {"description": "4x sizing", "measures": ["r4_fosc"]}
        }

    JSON objects keep their insertion order, so the manifest's order is the
    order the record's sub-tables appear in.
    """
    raw = manifest.get("topology_groups")
    if raw is None:
        return ()
    if not isinstance(raw, dict):
        raise ValueError(
            f"{path}: 'topology_groups' must be an object mapping a topology name to "
            "either a list of measurement names or an object with a 'measures' list"
        )

    known_set = set(known)
    groups: list[TopologyGroup] = []
    for name, spec in raw.items():
        if not name or not isinstance(name, str):
            raise ValueError(f"{path}: topology_groups keys must be non-empty strings")
        if name == UNGROUPED_TOPOLOGY:
            raise ValueError(
                f"{path}: topology name {UNGROUPED_TOPOLOGY!r} is reserved for the "
                "measurements no group claimed; pick another name"
            )
        description = ""
        if isinstance(spec, list):
            measures = spec
        elif isinstance(spec, dict):
            unknown_keys = sorted(set(spec) - set(TOPOLOGY_GROUP_KEYS))
            if unknown_keys:
                raise ValueError(
                    f"{path}: topology_groups[{name!r}] has unknown key(s) "
                    f"{unknown_keys}; supported keys are {list(TOPOLOGY_GROUP_KEYS)}"
                )
            if "measures" not in spec:
                raise ValueError(
                    f"{path}: topology_groups[{name!r}] must have a 'measures' list"
                )
            measures = spec["measures"]
            description = spec.get("description", "")
            if not isinstance(description, str):
                raise ValueError(
                    f"{path}: topology_groups[{name!r}].description must be a string"
                )
        else:
            raise ValueError(
                f"{path}: topology_groups[{name!r}] must be a list of measurement names "
                "or an object with a 'measures' list"
            )

        if not isinstance(measures, list) or not measures:
            raise ValueError(
                f"{path}: topology_groups[{name!r}] must list at least one measurement name"
            )
        # An unknown name here would silently cost the record a column, so it
        # is a hard error rather than something to skip over.
        missing = [m for m in measures if m not in known_set]
        if missing:
            raise ValueError(
                f"{path}: topology_groups[{name!r}] names measurement(s) {missing} that "
                "are not defined in 'measure' or 'raw_measures'"
            )
        groups.append(
            TopologyGroup(name=name, measures=tuple(measures), description=description)
        )
    return tuple(groups)


def load(directory: str | Path) -> Testbench:
    """Load a testbench manifest into a :class:`Testbench`.

    Accepts the experiment directory (``sim/<slug>/``), its ``testbench/``
    subdirectory, or the ``tb.json`` path itself.
    """
    directory = Path(directory).resolve()
    if directory.is_file() and directory.name == MANIFEST_NAME:
        directory = directory.parent
    if (directory / TESTBENCH_DIRNAME / MANIFEST_NAME).is_file():
        directory = directory / TESTBENCH_DIRNAME
    manifest_path = directory / MANIFEST_NAME
    if not manifest_path.is_file():
        raise FileNotFoundError(f"no {MANIFEST_NAME} in {directory}")

    manifest = json.loads(manifest_path.read_text())

    netlist = directory / _require(manifest, "netlist", manifest_path)
    if not netlist.is_file():
        raise FileNotFoundError(f"{manifest_path}: netlist {netlist} does not exist")

    measure, optional_measure = _load_measures(manifest, manifest_path)
    raw_measures, optional_raw = _load_raw_measures(manifest, manifest_path)
    optional_measures = frozenset(optional_measure | optional_raw)
    if not measure and not raw_measures:
        raise ValueError(
            f"{manifest_path}: must define at least one measurement in 'measure' "
            "or 'raw_measures'"
        )
    for key in list(measure) + list(raw_measures):
        if not key.replace("_", "").isalnum():
            raise ValueError(
                f"{manifest_path}: measurement name {key!r} must be alphanumeric/underscore "
                "(it becomes an ngspice vector/measure name)"
            )
    overlap = set(measure) & set(raw_measures)
    if overlap:
        raise ValueError(
            f"{manifest_path}: measurement name(s) {sorted(overlap)} defined in both "
            "'measure' and 'raw_measures'"
        )

    analyses = tuple(manifest.get("analyses", ("op",)))
    for name, rm in raw_measures.items():
        if not any(a.strip().split()[0] == rm.analysis for a in analyses if a.strip()):
            raise ValueError(
                f"{manifest_path}: raw_measures[{name!r}] declares analysis "
                f"{rm.analysis!r}, but 'analyses' does not include a {rm.analysis!r} "
                f"analysis ({analyses!r})"
            )

    dut = _load_dut(manifest, manifest_path)
    dut_export = _load_dut_export(manifest, manifest_path, directory)
    sweeps = _load_sweeps(manifest, manifest_path)
    grid_blocks = _load_grid_blocks(manifest, manifest_path, sweeps)
    raw_files = _load_raw_files(manifest, manifest_path)
    derived = _load_derived(
        manifest, manifest_path, directory, list(measure) + list(raw_measures)
    )

    topology_groups = _load_topology_groups(
        manifest,
        manifest_path,
        list(measure) + list(raw_measures) + list(derived.measures if derived else ()),
    )

    methodology = manifest.get("methodology", ())
    if isinstance(methodology, str):
        methodology = (methodology,) if methodology else ()
    else:
        methodology = tuple(methodology)

    tb = Testbench(
        directory=directory,
        name=manifest.get("name", directory.parent.name),
        netlist=netlist,
        description=manifest.get("description", ""),
        claim=manifest.get("claim", ""),
        methodology=methodology,
        nominal_supply_v=float(manifest.get("nominal_supply_v", DEFAULT_NOMINAL_SUPPLY_V)),
        supply_tolerance=float(manifest.get("supply_tolerance", DEFAULT_SUPPLY_TOLERANCE)),
        temperatures_c=tuple(
            float(t) for t in manifest.get("temperatures_c", DEFAULT_TEMPERATURES_C)
        ),
        corners=tuple(manifest.get("corners", (DEFAULT_CORNER_SET,))),
        extra_lib_sections=_load_extra_lib_sections(manifest, manifest_path),
        analyses=analyses,
        measure=measure,
        raw_measures=raw_measures,
        topology_groups=topology_groups,
        params={k: v for k, v in manifest.get("params", {}).items()},
        checks=dict(manifest.get("checks", {})),
        options=tuple(manifest.get("options", ())),
        dut=dut,
        dut_export=dut_export,
        sweeps=sweeps,
        grid_blocks=grid_blocks,
        optional_measures=optional_measures,
        raw_files=raw_files,
        derived=derived,
    )
    validate_netlist(tb)
    return tb


def validate_netlist(tb: Testbench) -> None:
    """Reject fragments -- and committed DUT exports -- that own what the harness owns.

    Catching this here is much friendlier than debugging a duplicated
    ``.end``, a hardcoded ``.temp 27`` that silently pins every corner to
    room temperature, or a hardcoded ``.measure`` that can never see a
    different corner's waveform.

    A ``dut`` export is held to the same rule: ``design/netlist.sh`` emits bare
    ``.subckt``/``.ends`` blocks, and an export that had picked up a ``.lib``
    or a ``.temp`` would pin every corner of every campaign that names it.

    Deliberately checks ``tb.dut`` (committed) and ``tb.netlist`` (the
    fragment) only -- NOT ``tb.netlist_sources``/``tb.resolved_dut``, which
    would resolve a ``dut_export`` right here, at ``load()`` time. A
    ``dut_export`` is checked by the same rule, but lazily, inside
    :meth:`DutExportSpec.resolve` -- the file does not exist yet for this
    function to read.
    """
    for source in tb.dut + (tb.netlist,):
        kind = "netlist fragments" if source == tb.netlist else "dut netlists"
        _check_forbidden_directives(source, kind)


def discover(root: str | Path) -> list[Path]:
    """Every experiment directory under ``root`` that owns a testbench.

    Looks for ``<root>/<experiment-slug>/testbench/tb.json`` and returns the
    ``<experiment-slug>`` directories, sorted.
    """
    root = Path(root)
    return sorted(
        p.parent.parent for p in root.glob(f"*/{TESTBENCH_DIRNAME}/{MANIFEST_NAME}")
    )
