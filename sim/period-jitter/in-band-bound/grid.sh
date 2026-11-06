#!/usr/bin/env bash
# gf180-pll :: period-jitter :: in-band-bound -- the 45-point grid.
#
# Thin wrapper over the shared staged driver; the stage plan lives in grid.json.
#
#   sim/period-jitter/in-band-bound/grid.sh [JOBS]      # default 2
#   sim/period-jitter/grid.py in-band-bound --plan      # list units, run nothing
#   sim/period-jitter/grid.py in-band-bound --backend batch [--batch-apply]
#
# `--resume` semantics, FAILED reporting and the exit status are unchanged: see
# sim/period-jitter/grid.py.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "${HERE}/../grid.py" in-band-bound --jobs "${1:-2}"
