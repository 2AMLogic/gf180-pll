#!/usr/bin/env bash
# Shared campaign-name enumeration for the sim/ CI hygiene checks.
#
# One campaign directory per sim/<name>/records/*.md evidence record. This
# lives in its own minimal file rather than sim/lib/simenv.sh because
# simenv.sh is scoped to corner-sweep/campaign-runner helpers (see its own
# header) -- it also sets `set -euo pipefail` and pins PDK environment
# variables, neither of which a CI hygiene check needs.
#
# Usage:
#   . "$(dirname "${BASH_SOURCE[0]}")/record-campaigns.sh"
#   mapfile -t campaigns < <(sim_record_campaigns "${REPO_ROOT}")
#
# shellcheck shell=bash

# sim_record_campaigns <repo_root>
#
# Prints one campaign name per line: the unique <name> in every
# sim/<name>/records/*.md path under <repo_root>/sim, sorted.
sim_record_campaigns() {
  local repo_root="$1"
  find "${repo_root}/sim" -path '*/records/*.md' -type f \
    | sed -E 's#.*/sim/([^/]+)/records/.*#\1#' | sort -u
}
