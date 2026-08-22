"""Tool discovery for the gf180mcu physical-verification flow.

Three things have to be located before either the DRC or the LVS deck can be
run, and all three are machine-local:

1. **The PDK** -- resolved by ``sim/harness/pdk.py`` (single-sourced on
   purpose; see that module for the full resolution order). The decks
   themselves live under ``<variant>/libs.tech/klayout/{drc,lvs}``.
2. **The KLayout application binary** -- *not* the ``klayout`` pip wheel. The
   foundry decks are Ruby DRC/LVS-DSL scripts; only the standalone KLayout
   binary can execute them (``klayout -b -r deck.drc``). The pip wheel gives
   ``klayout.db`` (used here for layout assembly) but has no DSL runner.
3. **A Python interpreter that can import both ``klayout`` and ``docopt``** --
   the PDK's own ``run_drc.py`` / ``run_lvs.py`` need them. That may or may
   not be the interpreter running this harness.

Every one of the three has an environment-variable override so a CI runner or
a differently-provisioned box never needs a code change:

    GF180_PDK_PATH / PDK_ROOT+PDK   -- see sim/harness/pdk.py
    KLAYOUT_BIN                     -- path to the KLayout application binary
    LAYOUT_PV_PYTHON                -- interpreter used to run the PDK runners
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LAYOUT_DIR = REPO_ROOT / "layout"
TOOLS_DIR = LAYOUT_DIR / "tools"


def _load_sim_pdk_module():
    """Load ``sim/harness/pdk.py`` by file path, not by ``sys.path`` + import.

    PDK discovery is sim/harness/pdk.py's job. Importing it (rather than
    copying it) is deliberate: two independent copies of the resolution
    order is exactly the kind of drift that makes a "clean" result
    unreproducible.

    This *cannot* be done the obvious way (``sys.path.insert(0, ".../sim")``
    then ``from harness import pdk``): ``sim/harness`` and ``layout/harness``
    are both top-level packages literally named ``harness``, so whichever one
    a caller imports first wins the ``sys.modules["harness"]`` slot and the
    second ``from harness import ...`` silently resolves against the wrong
    package (observed directly during bring-up -- a real caller doing
    ``sys.path.insert(0, ".../layout"); from harness import env`` before this
    module ran its own path shim raised ``ImportError: cannot import name
    'pdk' from 'harness'`` pointing at *this* package, not ``sim/harness``).
    Loading by explicit file path sidesteps the shared name entirely: the
    module lands under a private key in ``sys.modules``, never ``"harness"``.
    """
    module_name = "_gf180_layout_harness_sim_pdk"
    if module_name in importlib.util.sys.modules:
        return importlib.util.sys.modules[module_name]
    pdk_path = REPO_ROOT / "sim" / "harness" / "pdk.py"
    spec = importlib.util.spec_from_file_location(module_name, pdk_path)
    module = importlib.util.module_from_spec(spec)
    importlib.util.sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


sim_pdk = _load_sim_pdk_module()

PdkNotFound = sim_pdk.PdkNotFound
find_pdk = sim_pdk.find_pdk

# Where a KLayout application install typically lands, per platform. Checked
# only after $KLAYOUT_BIN and $PATH.
KLAYOUT_CANDIDATES = (
    "~/opt/klayout/klayout.app/Contents/MacOS/klayout",
    "/Applications/KLayout/klayout.app/Contents/MacOS/klayout",
    "/Applications/klayout.app/Contents/MacOS/klayout",
    "/usr/local/bin/klayout",
    "/usr/bin/klayout",
)

KLAYOUT_HINT = """\
The KLayout *application* binary was not found.

The gf180mcu DRC and LVS decks are Ruby DRC/LVS-DSL scripts; they are executed
by the standalone KLayout binary (`klayout -b -r <deck>`), not by the `klayout`
pip wheel. Install it, then either put it on PATH or point the harness at it:

    export KLAYOUT_BIN=/path/to/klayout

macOS note: a Homebrew-cask KLayout carries a com.apple.quarantine attribute
and is ad-hoc signed, so Gatekeeper blocks (in practice: *hangs*) headless
invocations. See layout/README.md -> "macOS: quarantine" for the fix.
"""

PV_PYTHON_HINT = """\
No Python interpreter with both `klayout` and `docopt` importable was found.

The PDK's own run_drc.py / run_lvs.py import them. Create one and point the
harness at it:

    python3 -m venv ~/opt/gf180pv-venv
    ~/opt/gf180pv-venv/bin/pip install klayout docopt
    export LAYOUT_PV_PYTHON=~/opt/gf180pv-venv/bin/python
"""


class ToolNotFound(RuntimeError):
    """Raised when a required physical-verification tool cannot be located."""


def _expand(path: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(path)))


def find_klayout() -> Path:
    """Locate the standalone KLayout application binary."""
    override = os.environ.get("KLAYOUT_BIN")
    if override:
        path = _expand(override)
        if not path.is_file():
            raise ToolNotFound(f"KLAYOUT_BIN={override} is not a file.\n\n{KLAYOUT_HINT}")
        return path

    on_path = shutil.which("klayout")
    if on_path:
        return Path(on_path)

    for candidate in KLAYOUT_CANDIDATES:
        path = _expand(candidate)
        if path.is_file():
            return path

    raise ToolNotFound(KLAYOUT_HINT)


def _imports_ok(python: Path) -> bool:
    try:
        subprocess.run(
            [str(python), "-c", "import klayout.db, docopt"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=60,
        )
    except (subprocess.SubprocessError, OSError):
        return False
    return True


def find_pv_python() -> Path:
    """Locate an interpreter that can run the PDK's run_drc.py / run_lvs.py."""
    override = os.environ.get("LAYOUT_PV_PYTHON")
    if override:
        path = _expand(override)
        if not _imports_ok(path):
            raise ToolNotFound(
                f"LAYOUT_PV_PYTHON={override} cannot import klayout and docopt.\n\n"
                + PV_PYTHON_HINT
            )
        return path

    candidates = [Path(sys.executable)]
    for name in ("python3", "python"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    candidates.append(_expand("~/opt/gf180pv-venv/bin/python"))

    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen or not candidate.is_file():
            continue
        seen.add(key)
        if _imports_ok(candidate):
            return candidate

    raise ToolNotFound(PV_PYTHON_HINT)


@dataclass(frozen=True)
class PvTools:
    """A located physical-verification toolchain."""

    pdk: "sim_pdk.Pdk"
    klayout: Path
    python: Path

    @property
    def drc_dir(self) -> Path:
        return self.pdk.klayout_dir / "drc"

    @property
    def lvs_dir(self) -> Path:
        return self.pdk.klayout_dir / "lvs"

    @property
    def drc_runner(self) -> Path:
        return self.drc_dir / "run_drc.py"

    @property
    def lvs_runner(self) -> Path:
        return self.lvs_dir / "run_lvs.py"

    @property
    def stdcell_gds(self) -> Path:
        lib = "gf180mcu_fd_sc_mcu9t5v0"
        return self.pdk.path / "libs.ref" / lib / "gds" / f"{lib}.gds"

    @property
    def variant_letter(self) -> str:
        """``gf180mcuD`` -> ``D``: the metal-stack option the decks switch on."""
        name = self.pdk.variant
        return name[-1].upper() if name and name[-1].upper() in "ABCD" else "D"

    def klayout_version(self) -> str:
        try:
            out = subprocess.run(
                [str(self.klayout), "-v"],
                capture_output=True,
                text=True,
                timeout=120,
                env=self.subprocess_env(),
            )
        except (subprocess.SubprocessError, OSError) as exc:  # pragma: no cover
            return f"unknown ({exc})"
        return (out.stdout or out.stderr).strip().splitlines()[0] if (out.stdout or out.stderr) else "unknown"

    def subprocess_env(self) -> dict:
        """Environment for the PDK runners.

        Two things are injected:

        * ``layout/tools`` on the front of PATH -- supplies the ``pmap`` shim
          the decks' logger needs on non-Linux hosts (see that script).
        * the KLayout binary's directory on PATH -- the PDK runners invoke a
          bare ``klayout`` via ``os.popen``/``check_call``, so it has to be
          findable by name even when we located it at an absolute path.
        """
        env = dict(os.environ)
        prefix = [str(TOOLS_DIR), str(self.klayout.parent)]
        env["PATH"] = os.pathsep.join(prefix + [env.get("PATH", "")])
        return env

    def provenance(self) -> dict:
        record = dict(self.pdk.provenance())
        record.update(
            {
                "klayout_binary": str(self.klayout),
                "klayout_version": self.klayout_version(),
                "pv_python": str(self.python),
                "variant_letter": self.variant_letter,
            }
        )
        return record


def run_pv_command(
    command: list,
    *,
    cwd: Path,
    timeout: int,
    env: dict,
    log_path: Path,
) -> tuple[subprocess.CompletedProcess, str]:
    """Run a PV-deck subprocess, capture combined stdout+stderr, and persist the log.

    Shared by ``drc.run()`` and ``lvs.run()`` -- the command list, cwd, timeout,
    environment, and log destination are the only things that differ between
    the two decks; everything else about invoking and logging a PV subprocess
    is identical.

    Raises ``subprocess.TimeoutExpired`` on timeout; the caller builds its own
    per-deck error ``Result`` from that, since the message text and dataclass
    differ between DRC and LVS.
    """
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(cwd),
        env=env,
    )
    log = (completed.stdout or "") + (completed.stderr or "")
    log_path.write_text(log)
    return completed, log


def find_tools(variant: str | None = None) -> PvTools:
    """Locate the whole toolchain, or raise ``PdkNotFound`` / ``ToolNotFound``."""
    pdk = find_pdk(variant)
    tools = PvTools(pdk=pdk, klayout=find_klayout(), python=find_pv_python())
    for required in (tools.drc_runner, tools.lvs_runner, tools.stdcell_gds):
        if not required.is_file():
            raise ToolNotFound(
                f"expected PDK file is missing: {required}\n"
                "The gf180mcu install looks incomplete -- reinstall it with volare."
            )
    return tools
