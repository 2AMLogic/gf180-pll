"""Drive the gf180mcu open-PDK KLayout LVS deck and normalise its result.

The deck is the PDK's -- ``libs.tech/klayout/lvs/run_lvs.py``, which drives
``gf180mcu.lvs`` through ``klayout -b -r``. As with DRC, this module supplies
the normalised verdict and a trustworthy exit code.

**The exit-code trap.** The PDK's ``run_lvs.py`` exits 0 on a *mismatch*. A
naive ``run_lvs.py ... && echo ok`` therefore reports success on a failing
LVS. This was observed directly during bring-up; both verdicts here are
decided from the deck's log markers, never from the process exit status.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import env as env_mod

MATCH_MARKER = "Congratulations! Netlists match"
MISMATCH_MARKER = "Netlists don't match"


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

    def as_dict(self) -> dict:
        return {
            "check": "lvs",
            "status": self.status,
            "topcell": self.topcell,
            "layout": str(self.layout),
            "netlist": str(self.netlist),
            "variant": self.variant,
            "extracted_netlist": str(self.extracted_netlist) if self.extracted_netlist else None,
            "message": self.message,
        }


def run(
    layout: Path,
    netlist: Path,
    topcell: str,
    run_dir: Path,
    tools: "env_mod.PvTools | None" = None,
    run_mode: str = "deep",
    substrate: str = "VSS",
    timeout: int = 3600,
) -> LvsResult:
    """Run the foundry LVS deck. Never raises on a *mismatch*.

    ``substrate`` maps to ``--lvs_sub``. It is not cosmetic: without it the
    extractor names the global p-substrate ``gf180mcu_gnd`` and exposes it as
    an extra top-level pin, so a schematic that (correctly) ties the n-channel
    bulk to VSS will not match. See layout/README.md.
    """
    tools = tools or env_mod.find_tools()
    layout = Path(layout).resolve()
    netlist = Path(netlist).resolve()
    run_dir = Path(run_dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    command = [
        str(tools.python),
        str(tools.lvs_runner),
        f"--layout={layout}",
        f"--netlist={netlist}",
        f"--variant={tools.variant_letter}",
        f"--topcell={topcell}",
        f"--run_dir={run_dir}",
        f"--run_mode={run_mode}",
        f"--lvs_sub={substrate}",
    ]

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(tools.lvs_dir),
            env=tools.subprocess_env(),
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

    log = (completed.stdout or "") + (completed.stderr or "")
    (run_dir / "lvs.stdout.log").write_text(log)

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
