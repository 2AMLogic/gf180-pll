#!/usr/bin/env bash
# gf180-pll :: run the simulation campaigns wired into this script
#
#   ./run-all.sh            full corner grids; every campaign below mints a new
#                           append-only record under sim/<slug>/records/
#   ./run-all.sh --check    nominal corner of each campaign, printed to stdout,
#                           nothing recorded -- the fast smoke test
#   SIM_JOBS=4 ./run-all.sh cap parallelism
#
# This is NOT every campaign under sim/. The script predates sim/harness and
# still covers only the campaigns listed below; the rest are run through
# `python3 sim/run_corners.py <slug-or-manifest-path>` (see
# sim/harness/README.md) or through their own testbench/run.sh. Retiring this
# script alongside sim/lib/simenv.sh, once every campaign has moved onto
# sim/harness, is #44.
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

# --------------------------------------------------------------------------
# Campaigns migrated onto sim/harness (#40): run through the shared corner
# runner, NOT through their superseded run.sh. `--check` maps to the harness's
# own debugging form -- nominal corner, nothing recorded.
#
#   run_harness <testbench-path-or-slug> [extra run_corners.py args ...]
# --------------------------------------------------------------------------
run_harness() {
  local target="$1"
  shift
  if [ -n "${MODE}" ]; then
    python3 "${HERE}/run_corners.py" "${target}" \
      --corners typical --temps 27 --supply-tol 0 --no-write "$@"
  else
    python3 "${HERE}/run_corners.py" "${target}" "$@"
  fi
}

# The passive-axis decks are a deliberate subset of the mandated PVT matrix
# (no MOS bundles, no supply axis -- see each record's Corner matrix field),
# and sim/README.md requires the reason to travel with the record.
CAP_SUBSET_REASON="Passive-axis campaign, not a MOS or supply campaign: the DUT is ten capacitors with no active devices, so the five MOS process bundles are N/A; the cap axes (mimcap_* and moscap_*) step together via the typical / all-fast / all-slow bundles, and each device depends only on its own axis, so every device still gets its full min/typ/max envelope. The voltage axis is this deck's own 0 -> 3.63 V C-V ramp, which already spans the whole 3.3 V +/-10% control range, so supply is the sweep variable rather than an independent corner axis."
RES_SUBSET_REASON="Passive-axis campaign, not a MOS or supply campaign: the DUT is seven poly resistors with no active devices, so the five MOS process bundles are N/A and only the res_* axis is meaningful; the voltage axis is this deck's own 0 -> 1.0 V device sweep, which measures the voltage coefficient directly, so supply is not an independent corner axis."

echo "=== devchar-delay ==="
run_harness devchar-delay
echo
echo "=== devchar-cp ==="
run_harness devchar-cp
echo
echo "=== devchar-passives (capacitors) ==="
run_harness "${HERE}/devchar-passives/testbench" --subset-reason "${CAP_SUBSET_REASON}"
echo
echo "=== devchar-passives (resistors) ==="
run_harness "${HERE}/devchar-passives/testbench-res" --subset-reason "${RES_SUBSET_REASON}"
echo

# Campaign order matters only in that a campaign must not depend on a later
# one's output; today none do. Each campaign mints its own append-only
# record(s).
#
# NOTE: these two invocations are the campaigns' PRE-migration runners. #41 has
# since moved both onto sim/harness -- divider-ratio by splitting into the
# sibling slugs divider-ratio-dff / -cell / -chain, lock-detector in place --
# so the citable evidence for either claim is now a harness-minted record, and
# these run.sh scripts are kept only because they are the only thing that can
# regenerate the extra CSV artifacts their own older records cite (see
# sim/README.md, "Migration state"). Repointing this loop at the harness is
# part of #44.
for campaign in divider-ratio lock-detector; do
  echo "=== ${campaign} ==="
  if [ -n "${MODE}" ]; then
    "${HERE}/${campaign}/testbench/run.sh" "${MODE}"
  else
    "${HERE}/${campaign}/testbench/run.sh"
  fi
  echo
done

echo "All campaigns wired into this script are complete."
