#!/usr/bin/env bash
# gf180-pll :: run every simulation campaign
#
#   ./run-all.sh            full corner grids, rewrites every results/*.csv
#   ./run-all.sh --check    nominal corner of each campaign, printed to stdout,
#                           nothing written -- the fast smoke test
#   SIM_JOBS=4 ./run-all.sh cap parallelism
#
# See README.md for the environment pin and the corner conventions.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/simenv.sh
. "${HERE}/lib/simenv.sh"

simenv_require_tools

echo "PDK      : $(simenv_pdk_variant) @ $(simenv_pdk_hash)"
echo "Simulator: $(simenv_ngspice_version)"
echo

MODE="${1:-}"
# Campaign order matters only in that a campaign must not depend on a later
# one's output; today none do (divider-ratio joins its own two sub-campaigns
# internally). Each campaign mints its own append-only record(s).
for campaign in devchar-delay devchar-cp devchar-passives divider-ratio lock-detector; do
  echo "=== ${campaign} ==="
  if [ -n "${MODE}" ]; then
    "${HERE}/${campaign}/testbench/run.sh" "${MODE}"
  else
    "${HERE}/${campaign}/testbench/run.sh"
  fi
  echo
done

echo "All campaigns complete."
