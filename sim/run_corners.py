#!/usr/bin/env python3
"""PVT corner runner for gf180-pll.

    python3 sim/run_corners.py --check-env
    python3 sim/run_corners.py --list
    python3 sim/run_corners.py harness-selftest

Stdlib only, no virtualenv required. See sim/README.md for the evidence
schema every run produces, and sim/harness/README.md for the testbench
manifest format.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
