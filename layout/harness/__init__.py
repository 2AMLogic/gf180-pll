"""Physical-verification (DRC/LVS) harness for gf180mcu.

Mirrors the structure of ``sim/harness``: a small importable package plus a
``run_pv.py`` CLI entry point at the directory root. Nothing here hardcodes a
PDK path -- PDK discovery is delegated to ``sim/harness/pdk.py`` so the two
harnesses can never disagree about which gf180mcu install is in use.

See ``layout/README.md`` for the flow this package automates.
"""

from __future__ import annotations

__all__ = ["env", "cell", "drc", "lvs", "faults"]
