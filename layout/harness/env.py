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


# The KLayout application version every DRC/LVS verdict this repository
# scores must be reproducible on. Why it matters: a KLayout newer than this
# pin (reproduced: 0.30.9) has been observed to report a false LVS mismatch
# on an LVS-clean, unchanged layout, while DRC on the same binary was
# unaffected (issue #360). See ``klayout_version_mismatch_warning()`` below
# and layout/README.md's "The two KLayouts" section.
#
# NOT "the version every committed log was captured against". This comment
# and the warning below both said that until 2026-09-28, and it was false:
# a census run for issue #127 found 16 of the 51 committed deck logs were
# captured on 0.30.9 or 0.30.10. What holds is narrower -- every block-level
# verdict has at least one log on this pin, and every remaining off-pin log
# is disclosed by name. ``layout/lib/check-layout-status-claims.sh`` derives
# both halves of that from the tree on every run; this module is only the
# single place the pin itself is declared.
#
# Update this by hand only when evidence is deliberately regenerated against
# a newer KLayout. The same check grades every document that restates the
# pin against this constant, so a bump fails the build until the prose in
# layout/README.md and the Chipalooza proposal follows it.
KNOWN_GOOD_KLAYOUT_VERSION = "KLayout 0.28.16"


def klayout_version_mismatch_warning(version: str) -> str | None:
    """Advisory-only comparison of a resolved KLayout version against the pin.

    Returns ``None`` (silent) when ``version`` matches
    ``KNOWN_GOOD_KLAYOUT_VERSION`` or when it could not be determined (the
    ``"unknown (...)"`` string produced by ``PvTools.klayout_version()``'s
    exception path) -- an undetermined version is not evidence of a
    mismatch, so it must not print a warning either. Otherwise returns a
    human-readable warning string; never raises.

    This is a pure string comparison, not semver parsing: the format
    (``"KLayout X.Y.Z"``) has been consistent across the platforms this
    repo has observed so far. Deliberately decoupled from any pass/fail
    verdict -- callers decide whether/when to surface it (see
    ``run_pv.py``'s ``cmd_check_env`` / ``cmd_drc`` / ``cmd_lvs``).
    """
    if not version or version.startswith("unknown"):
        return None
    if KNOWN_GOOD_KLAYOUT_VERSION in version:
        return None
    return (
        f"WARNING: resolved KLayout is '{version}', but this repo pins "
        f"'{KNOWN_GOOD_KLAYOUT_VERSION}' as the engine its scored DRC/LVS "
        "verdicts must be reproducible on. KLayout releases newer than the "
        "pin (reproduced: 0.30.9) have been observed to report a false LVS "
        "mismatch on an LVS-clean, unchanged layout -- DRC on the same "
        "binary was unaffected. A result produced here is not evidence "
        "about the pinned engine; see layout/README.md's \"The two "
        "KLayouts\" section before concluding a regression from an LVS "
        "mismatch alone."
    )


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

    def klayout_version_warning(self) -> str | None:
        """Advisory-only: see ``klayout_version_mismatch_warning()``."""
        return klayout_version_mismatch_warning(self.klayout_version())

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


#: Text artifacts a PV deck leaves in its run directory that embed absolute
#: paths (the report databases name the generated ``main.drc`` script, the
#: extracted netlist and LVS database name their inputs) and so are rewritten
#: by :func:`normalise_run_dir`. Binary layouts (``*.gds``) are never touched.
NORMALISED_GLOBS = ("*.log", "*.lyrdb", "*.lvsdb", "*.cir")

#: Name of the disclosure file :func:`normalise_run_dir` writes beside the
#: artifacts it rewrote, so the substitution is recorded rather than silent.
NORMALISATION_NOTE = "path-normalisation.txt"


def path_substitutions(run_dir: Path, pdk_path: Path | None = None) -> list:
    """Ordered ``(absolute path, token)`` pairs for :func:`normalise_paths`.

    Longest path first so a run directory nested inside the repo root (or the
    repo root inside the home directory) is replaced by its most specific
    token. Both the literal and the symlink-resolved spelling of each path are
    listed, because the decks echo whichever one they were handed.
    """
    pairs: list = []
    candidates = [(run_dir, "<RUN_DIR>"), (REPO_ROOT, "<REPO>")]
    if pdk_path is not None:
        candidates.append((pdk_path, "<PDK>"))
    candidates.append((Path.home(), "<HOME>"))
    for path, token in candidates:
        for spelling in {str(path), str(Path(path).resolve())}:
            if spelling and spelling != "/":
                pairs.append((spelling.rstrip("/"), token))
    pairs.sort(key=lambda pair: len(pair[0]), reverse=True)
    return pairs


def normalise_paths(text: str, substitutions: list) -> str:
    """Replace each host-absolute path in ``text`` with its stable token."""
    for path, token in substitutions:
        text = text.replace(path, token)
    return text


def normalise_run_dir(run_dir: Path, substitutions: list) -> int:
    """Rewrite a PV run directory's text artifacts in place; return the count.

    Called after a deck has run so that what gets captured as evidence names
    ``<RUN_DIR>`` / ``<REPO>`` / ``<PDK>`` / ``<HOME>`` instead of the
    generating host's directory layout (issue #701). The verdict markers the
    harness decides on are unaffected. The substitution is disclosed in
    ``path-normalisation.txt`` next to the artifacts it touched.
    """
    run_dir = Path(run_dir)
    rewritten = []
    for pattern in NORMALISED_GLOBS:
        for path in sorted(run_dir.glob(pattern)):
            original = path.read_text(errors="surrogateescape")
            normalised = normalise_paths(original, substitutions)
            if normalised != original:
                path.write_text(normalised, errors="surrogateescape")
                rewritten.append(path.name)
    tokens = sorted({token for _path, token in substitutions})
    note = [
        "Host-absolute paths in this bundle's text artifacts were replaced at",
        "capture time by the harness (layout/harness/env.py normalise_run_dir):",
        "",
        "  <RUN_DIR>  the directory the deck was run in",
        "  <REPO>     the repository checkout root the harness ran from",
        "  <PDK>      the installed gf180mcu PDK directory",
        "  <HOME>     the running user's home directory",
        "",
        "Tokens in use: " + ", ".join(tokens),
        "Files rewritten: " + (", ".join(rewritten) if rewritten else "(none)"),
        "Layout/netlist geometry and connectivity are untouched; only path",
        "strings in logs and report databases differ from the deck's raw output.",
        "",
    ]
    (run_dir / NORMALISATION_NOTE).write_text("\n".join(note))
    return len(rewritten)


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
