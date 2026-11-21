#!/usr/bin/env bash
# Derive, per statistical row, the `klt yield` sample-set documents and
# envelopes for T1 item 6 (#1081), from the committed Monte Carlo records.
#
#   bash signoff/yield/run.sh            # derive CSVs/limits, then re-run
#                                        # klt yield-csv + klt yield
#   KLT=... bash signoff/yield/run.sh    # use a specific klt binary
#
# Must run on the pinned klt release with the yield extra (klt-yield-native);
# signoff/run-signoff.sh's version check explains how to get one (a
# throwaway venv). The outputs under signoff/yield/samples/ and
# signoff/yield/reports/ are committed; CI grades the committed bytes via
# signoff/block-manifest.json, it does not re-run this script.
#
# The per-term spec limits live in signoff/yield/limits/ (written by
# derive.py); klt yield's --limits file wins over anything the sample-set
# carries, so the limits file is the single place each row's bound is
# stated. Paths passed to klt are repo-relative so the committed documents
# cite repo-relative sources.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"
KLT="${KLT:-klt}"

python3 signoff/yield/derive.py >/dev/null

gen() {
  local csv="$1" samples="$2" limits="$3" value="$4" group="$5" unit="$6"
  "$KLT" yield-csv "$csv" \
    --group-by "$group" --value "$value" --draw-col seed --unit "$unit" \
    --format json >"$samples"
  "$KLT" yield "$samples" --limits "$limits" --format json \
    >"signoff/yield/reports/$(basename "$samples")"
}

mkdir -p signoff/yield/samples signoff/yield/reports
gen signoff/yield/csv/mc-cp-term1-worst-window.csv \
  signoff/yield/samples/term1.json signoff/yield/limits/term1.json \
  mism_worst_pct corner "%"
gen signoff/yield/csv/mc-cp-term2a-wskew.csv \
  signoff/yield/samples/term2a.json signoff/yield/limits/term2a.json \
  wskew_s corner s
gen signoff/yield/csv/mc-cp-terms3-4.csv \
  signoff/yield/samples/term3.json signoff/yield/limits/term3.json \
  qnet0_c corner C
gen signoff/yield/csv/mc-cp-terms3-4.csv \
  signoff/yield/samples/term4.json signoff/yield/limits/term4.json \
  t_offset_s corner s
gen signoff/yield/csv/vco-adjacent-pair-ratio.csv \
  signoff/yield/samples/vco-adjacent-pair-ratio.json \
  signoff/yield/limits/vco-adjacent-pair-ratio.json \
  ratio point_id ""
echo "signoff/yield: 5 sample-set documents and envelopes (re)generated."
