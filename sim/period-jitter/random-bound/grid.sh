#!/usr/bin/env bash
# gf180-pll :: period-jitter :: random-bound -- the 45-point grid driver.
#
# Runs the once-only stages, then every PVT point of the mandated grid
# (sim/period-jitter/testbench/tb.json, via `run.py --list-points`), JOBS points
# side by side, each point one ngspice process at a time; then the reference
# point's validation and the summary.
#
#   sim/period-jitter/random-bound/grid.sh [JOBS]      # default 6
#
# `--resume` skips a stage whose result is already in results/ (so a stopped
# grid picks up where it stopped); delete results/ for a clean run.
#
# A failed point prints FAILED and the script exits non-zero after the rest
# finish; nothing is summarised over a partial grid without saying so --
# summarize.py lists every point it did not find.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JOBS="${1:-6}"
# One thread per ngspice: JOBS processes side by side must not each claim
# every core for model evaluation.
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
cd "${HERE}"
mkdir -p logs
python3 run.py --stage calibrate --stage loop
status=0
python3 run.py --list-points \
  | xargs -P "${JOBS}" -I{} sh -c \
      'python3 run.py --resume --point {} --stage trajectory --stage sid --stage bias --stage transient \
         > "logs/grid_{}.txt" 2>&1 || { echo "FAILED {}"; exit 1; }' \
  || status=1
python3 run.py --point typical_27c_3.30v --stage validate || status=1
python3 summarize.py > results/SUMMARY.md || status=1
exit "${status}"
