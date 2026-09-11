"""Drive the gf180mcu open-PDK KLayout LVS deck and normalise its result.

The deck is the PDK's -- ``libs.tech/klayout/lvs/run_lvs.py``, which drives
``gf180mcu.lvs`` through ``klayout -b -r``. As with DRC, this module supplies
the normalised verdict and a trustworthy exit code.

**The exit-code trap.** The PDK's ``run_lvs.py`` exits 0 on a *mismatch*. A
naive ``run_lvs.py ... && echo ok`` therefore reports success on a failing
LVS. This was observed directly during bring-up; both verdicts here are
decided from the deck's log markers, never from the process exit status.

**The poly-resistor process option.** gf180mcu's high-sheet poly resistors
(``ppolyf_u_1k``/``_2k``/``_3k``) are one drawn device -- identical masks --
separated only by a fab implant *option*, which the LVS deck models with its
``$poly_res`` switch. The PDK's own ``run_lvs.py`` hardcodes that switch to
``1k`` with no CLI override, so every run of it names a marked poly resistor
``ppolyf_u_1k`` whatever the design intends. :data:`POLY_RES` is this repo's
own ratified option (``3k``, see
``spec/decision-records/DR-009-vco-bias-resistor-device-class.md``) and is
applied through ``_pdk_lvs_poly_res.py``, a shim that re-uses the PDK
runner's own argument parsing and switch derivation and replaces exactly
that one key. Pass ``poly_res=None`` to get the PDK runner's own unmodified
behaviour.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import env as env_mod

MATCH_MARKER = "Congratulations! Netlists match"
MISMATCH_MARKER = "Netlists don't match"

POLY_RES = "3k"
"""This repo's ratified gf180mcu high-sheet-poly process option.

``design/netlist/vco.spice`` specifies ``ppolyf_u_3k`` for the VCO's three
bias resistors and every recorded ``sim/`` result was produced against that
device, so ``3k`` is the option the extracted netlist has to be named
against for a layout-vs-schematic comparison to mean anything. The drawn
geometry is the same for all three options (see
``layout/pll_top/vco/primitives.poly_resistor()``); the loop filter's own
resistor is the *unmarked* ``ppolyf_u`` class, which this switch does not
affect at all.
"""

_POLY_RES_SHIM = Path(__file__).resolve().parent / "_pdk_lvs_poly_res.py"


@dataclass
class LvsResult:
    status: str  # "match" | "mismatch" | "error"
    topcell: str
    layout: Path
    netlist: Path
    variant: str
    log: str = ""
    extracted_netlist: Path | None = None
    lvs_db: Path | None = None
    command: list = field(default_factory=list)
    runner_returncode: int | None = None
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "match"

    def summary(self) -> str:
        if self.status == "match":
            return f"LVS match: {self.topcell} ({self.variant}) layout == schematic"
        if self.status == "mismatch":
            return f"LVS mismatch: {self.topcell} ({self.variant}) layout != schematic"
        return f"LVS error: {self.message}"


def run(
    layout: Path,
    netlist: Path,
    topcell: str,
    run_dir: Path,
    tools: "env_mod.PvTools | None" = None,
    run_mode: str = "deep",
    substrate: str = "VSS",
    timeout: int = 3600,
    poly_res: str | None = POLY_RES,
) -> LvsResult:
    """Run the foundry LVS deck. Never raises on a *mismatch*.

    ``substrate`` maps to ``--lvs_sub``. It is not cosmetic: without it the
    extractor names the global p-substrate ``gf180mcu_gnd`` and exposes it as
    an extra top-level pin, so a schematic that (correctly) ties the n-channel
    bulk to VSS will not match. See layout/README.md.

    ``poly_res`` selects the deck's high-sheet poly-resistor process option
    (see :data:`POLY_RES`); ``None`` runs the PDK's own ``run_lvs.py``
    directly, with its hardcoded ``1k``.
    """
    tools = tools or env_mod.find_tools()
    layout = Path(layout).resolve()
    netlist = Path(netlist).resolve()
    run_dir = Path(run_dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    runner: list[str] = (
        [str(tools.lvs_runner)]
        if poly_res is None
        else [str(_POLY_RES_SHIM), str(tools.lvs_runner), poly_res]
    )
    command = [
        str(tools.python),
        *runner,
        f"--layout={layout}",
        f"--netlist={netlist}",
        f"--variant={tools.variant_letter}",
        f"--topcell={topcell}",
        f"--run_dir={run_dir}",
        f"--run_mode={run_mode}",
        f"--lvs_sub={substrate}",
    ]

    try:
        completed, log = env_mod.run_pv_command(
            command,
            cwd=tools.lvs_dir,
            timeout=timeout,
            env=tools.subprocess_env(),
            log_path=run_dir / "lvs.stdout.log",
        )
    except subprocess.TimeoutExpired as exc:  # pragma: no cover - operational
        return LvsResult(
            status="error",
            topcell=topcell,
            layout=layout,
            netlist=netlist,
            variant=tools.variant_letter,
            command=command,
            message=f"LVS run timed out after {timeout}s: {exc}",
        )

    extracted = sorted(run_dir.glob("*.cir"))
    lvs_dbs = sorted(run_dir.glob("*.lvsdb"))

    common = {
        "topcell": topcell,
        "layout": layout,
        "netlist": netlist,
        "variant": tools.variant_letter,
        "log": log,
        "extracted_netlist": extracted[0] if extracted else None,
        "lvs_db": lvs_dbs[0] if lvs_dbs else None,
        "command": command,
        "runner_returncode": completed.returncode,
    }

    if MISMATCH_MARKER in log:
        return LvsResult(status="mismatch", **common)
    if MATCH_MARKER in log:
        return LvsResult(status="match", **common)
    return LvsResult(
        status="error",
        message=(
            "LVS deck produced neither a match nor a mismatch verdict "
            f"(runner exit {completed.returncode}); see the captured log"
        ),
        **common,
    )
