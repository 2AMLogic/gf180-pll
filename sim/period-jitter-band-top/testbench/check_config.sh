#!/usr/bin/env bash
# gf180-pll :: period-jitter-band-top :: verify tb.json's configuration bits
# against sim/lib/pll_top_dut.sh, the single owner of that encoding.
#
# WHY THIS EXISTS.  sim/lib/pll_top_dut.sh owns what `pll_top`'s 22 static
# configuration bits MEAN.  `divider_chain.sch`'s one-hot SEL / binary P
# encoding is easy to get subtly wrong in a way that still locks, at the wrong
# N -- and a period-jitter number taken at the wrong N is not wrong-looking,
# it is just wrong.  A JSON manifest cannot call a bash function, so the codes
# are written into tb.json and this script asserts they are EXACTLY what the
# helper produces.
#
# This campaign checks one thing sim/reference-spur's equivalent does not: its
# VCO band code is NOT fixed.  spec/pll.md's band-selection rule puts 34 of
# the 45 PVT points in band 6 and 11 in band 7 at 200 MHz, so the band bits
# live per point on the manifest's `op` sweep axis.  Every one of those points
# is checked here against `cloop_band_params` for the band its own point id
# names -- an id that says `b7` while carrying band 6's bits would otherwise
# read correctly and simulate wrongly.
#
#   ./check_config.sh      # prints each field and a PASS/FAIL verdict
#
# Exit 0 if every bit matches, 1 otherwise.  What this does NOT check is
# whether the per-corner band assignment is the one the ratified rule
# selects -- that is band_and_vstart_from_vco_record.py --check's job, and
# sim/tests/test_period_jitter_band_top_grid.py runs it in CI.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${HERE}/../../.." && pwd)"

# shellcheck source=/dev/null
. "${ROOT}/sim/lib/pll_top_dut.sh"

# The check itself lives in sim/lib/pll_top_dut.sh, shared with the other
# band-top campaigns.
cloop_check_band_top_config "${HERE}/tb.json" "${HERE}/tb_period_jitter_band_top.sp"
