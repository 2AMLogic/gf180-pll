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
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from .corners import (
    DEFAULT_CORNER_SET,
    DEFAULT_NOMINAL_SUPPLY_V,
    DEFAULT_SUPPLY_TOLERANCE,
    DEFAULT_TEMPERATURES_C,
)

MANIFEST_NAME = "tb.json"

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


@dataclass
class RawMeasure:
    analysis: str
    expr: str


@dataclass
class TopologyGroup:
    """One sub-circuit / topology's slice of a testbench's measurements.

    Only the *record* consumes this: the deck, the sweep and the checks are
    all indifferent to grouping.
    """

    name: str
    measures: tuple[str, ...]
    description: str = ""


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
    def measure_names(self) -> list[str]:
        """Every measurement name, ``measure`` then ``raw_measures``, in order."""
        return list(self.measure) + list(self.raw_measures)

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

    def provenance(self) -> dict:
        return {
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


def _require(manifest: dict, key: str, path: Path):
    if key not in manifest:
        raise ValueError(f"{path}: missing required key {key!r}")
    return manifest[key]


def _load_raw_measures(manifest: dict, path: Path) -> dict[str, RawMeasure]:
    raw: dict[str, RawMeasure] = {}
    for name, spec in manifest.get("raw_measures", {}).items():
        if not isinstance(spec, dict) or "expr" not in spec:
            raise ValueError(
                f"{path}: raw_measures[{name!r}] must be an object with at least "
                "an 'expr' key (e.g. {\"analysis\": \"tran\", \"expr\": \"trig ... targ ...\"})"
            )
        raw[name] = RawMeasure(analysis=spec.get("analysis", "tran"), expr=spec["expr"])
    return raw


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

    measure = dict(manifest.get("measure", {}))
    raw_measures = _load_raw_measures(manifest, manifest_path)
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

    topology_groups = _load_topology_groups(
        manifest, manifest_path, list(measure) + list(raw_measures)
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
    )
    validate_netlist(tb)
    return tb


def validate_netlist(tb: Testbench) -> None:
    """Reject fragments that try to own what the harness owns.

    Catching this here is much friendlier than debugging a duplicated
    ``.end``, a hardcoded ``.temp 27`` that silently pins every corner to
    room temperature, or a hardcoded ``.measure`` that can never see a
    different corner's waveform.
    """
    problems: list[str] = []
    for lineno, raw in enumerate(tb.netlist.read_text().splitlines(), start=1):
        line = raw.strip().lower()
        if not line.startswith("."):
            continue
        directive = line.split()[0]
        if directive in FORBIDDEN_DIRECTIVES:
            problems.append(f"  line {lineno}: {raw.strip()}")
    if problems:
        raise ValueError(
            f"{tb.netlist}: netlist fragments must not contain "
            f"{', '.join(FORBIDDEN_DIRECTIVES)} -- the harness supplies the models, "
            "corner libs, temperature, measurements and the control block:\n"
            + "\n".join(problems)
        )


def discover(root: str | Path) -> list[Path]:
    """Every experiment directory under ``root`` that owns a testbench.

    Looks for ``<root>/<experiment-slug>/testbench/tb.json`` and returns the
    ``<experiment-slug>`` directories, sorted.
    """
    root = Path(root)
    return sorted(
        p.parent.parent for p in root.glob(f"*/{TESTBENCH_DIRNAME}/{MANIFEST_NAME}")
    )
