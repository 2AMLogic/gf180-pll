"""gf180mcu PDK discovery.

No PDK path is ever hardcoded into a netlist or a testbench. Everything
resolves through this module so that the harness runs unchanged on a
developer box, a CI runner, or a fresh agent container.

Resolution order (first hit wins) -- unchanged from the ported
``2AMLogic/gf180-bandgap`` pattern and from the interim ``sim/lib/simenv.sh``
shim's single ``GF180_PDK_ROOT`` override, now generalized:

1. ``GF180_PDK_PATH``   -- absolute path to the *variant* directory
                           (the one containing ``libs.tech/``), e.g.
                           ``~/.ciel/gf180mcuD``.
2. ``GF180_PDK_ROOT``   -- back-compat with the interim shim: the variant
                           directory itself (same shape as GF180_PDK_PATH).
3. ``PDK_ROOT`` (+ ``PDK``, default ``gf180mcuD``) -- the conventional
                           open_pdks / ciel / OpenLane environment.
4. ``sim/pdk.local.json`` -- machine-local override, git-ignored.
5. ``sim/pdk.json``      -- committed defaults: variant + search roots.
6. Built-in search roots -- ciel store (then the legacy volare store), open_pdks
                           install prefixes.

Whichever tree is resolved, its ``SOURCES`` open_pdks revision must equal the
``open_pdks`` pin in the committed ``sim/pdk.json``. A tree at any other
revision is never returned: an explicit override at the wrong revision raises
:class:`PdkRevisionMismatch` immediately, and a search that finds only
wrong-revision trees raises it after listing them. (``sim/pdk.local.json``
cannot move the pin -- records must be reproducible from provenance alone.)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SIM_DIR = REPO_ROOT / "sim"

DEFAULT_VARIANT = "gf180mcuD"

# Search roots used when nothing else pins the PDK down. Each is a directory
# that is expected to *contain* variant directories (gf180mcuA..D).
BUILTIN_SEARCH_ROOTS = (
    "~/.ciel",
    "~/.volare",
    "/usr/share/pdk",
    "/usr/local/share/pdk",
    "~/share/pdk",
    "/opt/pdk",
)

INSTALL_HINT = """\
gf180mcu PDK not found.

Install it with ciel (recommended, ~5 GB), at the revision pinned in sim/pdk.json:

    pip install ciel
    ciel enable --pdk-family gf180mcu -l gf180mcu_fd_pr <open_pdks-hash>

ciel installs into ~/.ciel/<variant> and this harness finds it there
automatically. If your PDK lives somewhere else, point the harness at it:

    export GF180_PDK_PATH=/path/to/gf180mcuD        # variant dir, contains libs.tech/
    # or the conventional pair:
    export PDK_ROOT=/path/to/pdk-root
    export PDK=gf180mcuD

...or commit-free machine-local config in sim/pdk.local.json:

    {"variant": "gf180mcuD", "search_roots": ["/my/pdks"]}

Whatever its location, the tree must be at the open_pdks revision pinned in
sim/pdk.json.
"""


class PdkNotFound(RuntimeError):
    """Raised when no usable gf180mcu install can be located."""


class PdkRevisionMismatch(PdkNotFound):
    """Raised when the only install(s) found are not at the pinned revision.

    A subclass of :class:`PdkNotFound` so every caller that already turns a
    missing PDK into an environment error treats a stale tree the same way.
    """


@dataclass(frozen=True)
class Pdk:
    """A located gf180mcu install."""

    path: Path          # .../gf180mcuD
    variant: str        # gf180mcuD
    source: str         # how we found it (for provenance in results)

    @property
    def ngspice_dir(self) -> Path:
        return self.path / "libs.tech" / "ngspice"

    @property
    def xschem_dir(self) -> Path:
        return self.path / "libs.tech" / "xschem"

    @property
    def klayout_dir(self) -> Path:
        return self.path / "libs.tech" / "klayout"

    @property
    def design_include(self) -> Path:
        """Global switches / corner params. Must be included before models."""
        return self.ngspice_dir / "design.ngspice"

    @property
    def model_lib(self) -> Path:
        """Main device model library (``.lib <section>`` sections)."""
        return self.ngspice_dir / "sm141064.ngspice"

    @property
    def version(self) -> str:
        """open_pdks commit recorded in ``SOURCES``, or 'unknown'."""
        sources = self.path / "SOURCES"
        if sources.is_file():
            for line in sources.read_text().splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[0] == "open_pdks":
                    return parts[1]
            text = sources.read_text().strip()
            if text:
                return text.splitlines()[0].strip()
        return "unknown"

    def provenance(self) -> dict:
        return {
            "path": str(self.path),
            "variant": self.variant,
            "open_pdks_version": self.version,
            "discovered_via": self.source,
        }


def _is_valid_variant_dir(path: Path) -> bool:
    return (path / "libs.tech" / "ngspice" / "sm141064.ngspice").is_file()


def _load_config() -> dict:
    """Merge sim/pdk.json with sim/pdk.local.json (local wins)."""
    config: dict = {}
    for name in ("pdk.json", "pdk.local.json"):
        candidate = SIM_DIR / name
        if candidate.is_file():
            try:
                config.update(json.loads(candidate.read_text()))
            except json.JSONDecodeError as exc:  # pragma: no cover - config typo
                raise RuntimeError(f"{candidate} is not valid JSON: {exc}") from exc
    return config


def _expand(path: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(path)))


def pinned_open_pdks() -> str | None:
    """The open_pdks revision pinned in the committed ``sim/pdk.json``.

    Deliberately read from the committed file alone, never from
    ``sim/pdk.local.json`` or the environment: the pin is what makes a record
    reproducible from its provenance.
    """
    committed = SIM_DIR / "pdk.json"
    if not committed.is_file():
        return None
    try:
        pin = json.loads(committed.read_text()).get("open_pdks")
    except json.JSONDecodeError as exc:  # pragma: no cover - config typo
        raise RuntimeError(f"{committed} is not valid JSON: {exc}") from exc
    return pin or None


def _revision_problem(pdk: Pdk, pin: str | None) -> str | None:
    """A one-line description of a pin mismatch, or None if ``pdk`` matches."""
    if pin is None or pdk.version == pin:
        return None
    return (
        f"{pdk.path} is at open_pdks {pdk.version}, "
        f"but sim/pdk.json pins open_pdks {pin}"
    )


def _mismatch_error(problems: list[str], pin: str | None) -> PdkRevisionMismatch:
    return PdkRevisionMismatch(
        "gf180mcu PDK found, but not at the pinned open_pdks revision:\n  %s\n\n"
        "Records must be reproducible from their provenance, so a PDK tree at a\n"
        "different revision is refused rather than used silently. Install the pin:\n\n"
        "    ciel enable --pdk-family gf180mcu -l gf180mcu_fd_pr %s\n\n"
        "(and remove or ignore any stale ~/.volare tree)."
        % ("\n  ".join(problems), pin)
    )


def find_pdk(variant: str | None = None) -> Pdk:
    """Locate a gf180mcu install, or raise :class:`PdkNotFound`."""
    config = _load_config()
    variant = variant or os.environ.get("PDK") or config.get("variant") or DEFAULT_VARIANT
    pin = pinned_open_pdks()

    direct = os.environ.get("GF180_PDK_PATH")
    if direct:
        path = _expand(direct)
        if not _is_valid_variant_dir(path):
            raise PdkNotFound(
                f"GF180_PDK_PATH={direct} does not look like a gf180mcu variant "
                f"directory (expected {path}/libs.tech/ngspice/sm141064.ngspice).\n\n"
                + INSTALL_HINT
            )
        found = Pdk(path=path, variant=path.name, source="GF180_PDK_PATH")
        if problem := _revision_problem(found, pin):
            raise _mismatch_error([problem], pin)
        return found

    tried: list[str] = []

    # Back-compat with the interim sim/lib/simenv.sh shim's own override.
    legacy_root = os.environ.get("GF180_PDK_ROOT")
    if legacy_root:
        path = _expand(legacy_root)
        tried.append(str(path))
        if _is_valid_variant_dir(path):
            found = Pdk(path=path, variant=path.name, source="GF180_PDK_ROOT")
            if problem := _revision_problem(found, pin):
                raise _mismatch_error([problem], pin)
            return found

    pdk_root = os.environ.get("PDK_ROOT")
    if pdk_root:
        path = _expand(pdk_root) / variant
        tried.append(str(path))
        if _is_valid_variant_dir(path):
            found = Pdk(path=path, variant=variant, source="PDK_ROOT")
            if problem := _revision_problem(found, pin):
                raise _mismatch_error([problem], pin)
            return found

    roots = list(config.get("search_roots") or ()) + list(BUILTIN_SEARCH_ROOTS)
    stale: list[str] = []
    for root in roots:
        path = _expand(root) / variant
        tried.append(str(path))
        if _is_valid_variant_dir(path):
            found = Pdk(path=path, variant=variant, source=f"search_root:{root}")
            if problem := _revision_problem(found, pin):
                stale.append(problem)
                continue
            return found

    if stale:
        raise _mismatch_error(stale, pin)
    raise PdkNotFound(
        "Looked for gf180mcu variant %r in:\n  %s\n\n%s"
        % (variant, "\n  ".join(tried), INSTALL_HINT)
    )
