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


@dataclass
class RawMeasure:
    analysis: str
    expr: str


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
    analyses: tuple[str, ...] = ("op",)
    measure: dict[str, str] = field(default_factory=dict)
    raw_measures: dict[str, RawMeasure] = field(default_factory=dict)
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
        analyses=analyses,
        measure=measure,
        raw_measures=raw_measures,
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
