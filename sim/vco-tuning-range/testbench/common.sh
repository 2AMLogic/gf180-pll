#!/usr/bin/env bash
# gf180-pll :: vco-tuning-range :: helpers shared by the supply and stage-count
# runners.
#
# `run.sh` (the open-loop f(Vctrl) campaign) carries its own copies of these two
# functions inline. They are duplicated here rather than refactored out of it
# because `run.sh` is the script that minted the tuning-range record: editing it
# would make the committed runner differ from the one that produced the
# evidence, for no behavioural gain. If a third consumer appears, fold all three
# together in one change and re-run the affected campaigns.
#
# shellcheck shell=bash

# Map a corner-bundle name to the `.lib` sections it stands for.
#
# The five MOS-only bundles leave the passive sections at typical, which
# sim/README.md warns is a silent omission for any claim whose value rides on
# R or C. This DUT's frequency is set by a poly resistor, so the two composite
# bundles exist to sweep that axis explicitly.
bundle_libs() {
  case "$1" in
    all-slow) echo "ss,res_ss,moscap_ss" ;;
    all-fast) echo "ff,res_ff,moscap_ff" ;;
    *)        echo "$1,res_typical,moscap_typical" ;;
  esac
}

# Frequency estimate used ONLY to size transient windows -- never to produce a
# result. Calibrated against the nominal corner of the tuning campaign; the
# corner factors bound the measured spread with margin, and every runner
# validates its own measurement, so an inaccurate estimate costs runtime,
# never correctness.
#   f_est <band> <vctrl> <bundle> <temp> <vdd>
f_est() {
  python3 - "$@" <<'PY'
import sys
band, vctrl, bundle, temp, vdd = int(sys.argv[1]), float(sys.argv[2]), sys.argv[3], float(sys.argv[4]), float(sys.argv[5])
ftemp = {-40.0: 0.75, 27.0: 1.0, 125.0: 1.35}[temp]
fres  = {"all-fast": 1.25, "all-slow": 0.80}.get(bundle, 1.0)
fvdd  = 1.0 + (3.30 - vdd) * 0.36
print("%.6g" % (4.5e6 * (1.65 ** band) * (1 + (vctrl - 0.9) / 1.33) * ftemp * fres * fvdd))
PY
}

# Tag used for a run directory: filesystem-safe, collision-free.
#   run_tag <field> [<field> ...]
run_tag() {
  local t
  t="$(printf '%s_' "$@")"
  t="${t%_}"
  t="${t//./p}"
  t="${t//-/m}"
  echo "${t}"
}
