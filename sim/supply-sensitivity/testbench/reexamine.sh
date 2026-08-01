#!/usr/bin/env bash
# gf180-pll :: supply-sensitivity :: re-examine a record against the
# closed-loop internal-timestep bound (#69)
#
#   ./reexamine.sh <record-id> [outdir]
#
# Why this exists as a script rather than as prose in a record.  This
# campaign's 9-corner record `20260801-024935-c4fe724` was taken at a 400 ps
# internal-timestep ceiling.  `sim/README.md`'s "Closed-loop internal-timestep
# bound" says 100 ps, because the PFD's internal SR-latch set pulse is
# 0.33-0.39 ns and a ceiling ABOVE that lets ngspice step clean over the pulse
# -- at which point the PFD stops seeing feedback edges and the loop reports a
# confident, clean-looking "does not lock" that is an artefact of the
# integration.  400 ps is above the pulse.  So every verdict in that record
# needs re-examining, and the re-examination has to be REPRODUCIBLE rather than
# a paragraph of assertion: `sim/README.md` forbids hand-typed numbers in a
# record for exactly the reason that they drift away from the data.
#
# What it does NOT do: it does not re-simulate, and it cannot produce the
# corrected values.  Only a re-run at the bound can do that (see the record
# this emits).  What it CAN do is decide, from committed evidence alone,
# whether each recorded verdict carries the artefact's signature -- which is
# what decides whether a re-run is required and which verdicts must not be
# cited meanwhile.
#
# The signature, from `sim/pll-top-smoke/records/20260801-085349-0e5c22d.md`
# (#52) and `sim/README.md`: the loop "reads as jammed with UP asserted,
# ramping Vctrl to the rail while the feedback is ALREADY faster than the
# reference".  Both halves are measurable from the committed
# corners/<id>/supply_steady.csv:
#
#   1. Is the feedback faster than the reference?
#      f_fb = f_out / nmeas (nmeas is the MEASURED divide ratio, so this does
#      not assume the divider worked), compared against this campaign's f_ref.
#   2. Is Vctrl being driven the WRONG way?  Compared against #8's INDEPENDENT
#      open-loop f(Vctrl) table -- the same committed evidence the campaign
#      derives its warm start from.  That table says which Vctrl produces the
#      target frequency at this corner.  A loop whose late-window Vctrl sits
#      well ABOVE that value, while its feedback is already too FAST, is being
#      driven away from lock by a detector that is not seeing the feedback.
#   3. Had the run settled at all?  The late-window Vctrl spread
#      (vctrl_max - vctrl_min) separates a settled row from a ramping one
#      without needing to know where the run started.
#
# A row is classified as:
#   ARTEFACT-DIVERGING   feedback fast AND Vctrl driven above the predicted
#                        operating point AND still moving -- the signature.
#   ARTEFACT-DETECTOR    settled at the right frequency, but the design's own
#                        LOCK flag never asserted.  lock_detector is driven
#                        from UP/DN, so an integrator that steps over the PFD
#                        pulses cannot produce LOCK even for a locked loop.
#   CONSISTENT           settled, on frequency, LOCK asserted, Vctrl at the
#                        independently-predicted value.  Nothing to re-examine.
#   UNCLASSIFIED         none of the above patterns fit; says so rather than
#                        forcing a row into a bucket.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP="$(cd "${HERE}/.." && pwd)"
ROOT="$(cd "${EXP}/../.." && pwd)"

RID="${1:?usage: reexamine.sh <record-id> [outdir]}"
OUT="${2:-${EXP}/corners/${RID}-reexam}"

CSV="${EXP}/corners/${RID}/supply_steady.csv"
[ -f "${CSV}" ] || { echo "ERROR: ${CSV} not found" >&2; exit 1; }

# Re-read the campaign's own constants rather than restating them -- the same
# trick report.sh uses, and for the same reason: a threshold restated here is a
# threshold that will drift away from the one the campaign actually applied.
# shellcheck source=../../lib/simenv.sh
. "${ROOT}/sim/lib/simenv.sh"
eval "$(sed -n '/^KFOUT=/,/^ACC_FDEV_PPM=/p;/^VCO_TUNING=/p' "${HERE}/run.sh")"

# Thresholds for the classification above.  Stated here, before the analysis.
# FFB_FAST     |f_fb/f_ref - 1| above which the feedback is "already faster".
#              1e-3 is ACC_FERR, the campaign's own lock criterion -- not a new
#              number invented for this analysis.
# VC_DRIVEN    how far above #8's predicted operating point Vctrl must sit to
#              count as "driven the wrong way", in volts.  0.1 V is ~20x the
#              largest deviation seen on any row that PASSED (see the emitted
#              table), i.e. deliberately far outside the agreement band the
#              compliant rows themselves establish.
# VC_SETTLED   late-window Vctrl spread below which a row counts as settled.
#              0.05 V is ~7x the largest spread on any PASS row.
FFB_FAST="${ACC_FERR}"
VC_DRIVEN=0.10
VC_SETTLED=0.05

mkdir -p "${OUT}"

# #8's f(Vctrl) table -> the control voltage that produces KFOUT at each
# (bundle, temperature, supply).  Linear interpolation inside the one
# bracketing interval of the MEASURED curve, never extrapolated -- the same
# derivation run.sh's derive_op_points uses, kept identical on purpose so this
# analysis and the campaign cannot disagree about the predicted operating point.
predict() {
  awk -F, -v target="${KFOUT}" '
    !/^#/ && $1 != "bundle" {
      b=$1; t=$2; v=$3; bd=$4; vc=$5; f=$6;
      if (b == "all-slow" || b == "all-fast") next;
      k = b "|" t "|" v "|" bd; n[k]++; VC[k,n[k]]=vc; F[k,n[k]]=f;
    }
    END {
      for (k in n) for (i = 1; i < n[k]; i++) {
        f1 = F[k,i]; f2 = F[k,i+1];
        if ((f1 - target) * (f2 - target) <= 0 && f1 != f2)
          printf "%s %.6f\n", k, VC[k,i] + (target - f1) * (VC[k,i+1] - VC[k,i]) / (f2 - f1);
      }
    }' "${VCO_TUNING}"
}

PRED="${OUT}/predicted_vctrl.txt"
predict >"${PRED}"

TABLE="${OUT}/reexamination.csv"
{
  echo "# campaign: supply-sensitivity"
  echo "# re-examined record: ${RID}"
  echo "# generated_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "# source (read-only, never modified): corners/${RID}/supply_steady.csv"
  echo "# predicted vctrl source: ${VCO_TUNING#"${ROOT}/"} (#8, open-loop f(Vctrl))"
  echo "# f_ref_hz: ${KFREF}; f_out target: ${KFOUT}"
  echo "# thresholds: ffb_fast=${FFB_FAST} (= ACC_FERR), vc_driven=${VC_DRIVEN} V, vc_settled=${VC_SETTLED} V"
  echo "# NO SIMULATION WAS RUN. Every column is arithmetic on committed data."
  echo "bundle,temp_c,vdd_v,band,recorded_verdict,fout_hz,nmeas,ffb_hz,ffb_rel_err,lock_lvl_v,vctrl_avg_v,vctrl_spread_v,vctrl_predicted_v,vctrl_excess_v,settled,classification"
  awk -F, -v fref="${KFREF}" -v fast="${FFB_FAST}" -v drv="${VC_DRIVEN}" \
          -v set="${VC_SETTLED}" -v predfile="${PRED}" '
    function abs(x) { return x < 0 ? -x : x }
    BEGIN { while ((getline line < predfile) > 0) { split(line, a, " "); P[a[1]] = a[2] } }
    !/^#/ && $1 != "bundle" {
      bundle=$1; temp=$2; vdd=$3; band=$4; fout=$5+0; ferr=$7+0; nm=$13+0;
      vca=$14+0; vcmin=$15+0; vcmax=$16+0; lock=$17+0; verdict=$22;
      ffb = (nm != 0) ? fout / nm : 0;
      rel = (ffb - fref) / fref;
      spread = vcmax - vcmin;
      key = bundle "|" temp "|" sprintf("%.2f", vdd + 0) "|" band;
      vp = (key in P) ? P[key] : "";
      exc = (vp == "") ? "" : vca - vp;
      settled = (spread <= set) ? "yes" : "no";
      cls = "UNCLASSIFIED";
      if (verdict == "PASS" && settled == "yes" && abs(rel) <= fast) cls = "CONSISTENT";
      else if (rel > fast && settled == "no" && vp != "" && exc > drv) cls = "ARTEFACT-DIVERGING";
      else if (settled == "yes" && abs(rel) <= fast && lock < 0.5 * vdd) cls = "ARTEFACT-DETECTOR";
      printf "%s,%s,%s,%s,%s,%.6g,%.6g,%.6g,%+.4g,%.4g,%.4f,%.4f,%s,%s,%s,%s\n",
        bundle, temp, vdd, band, verdict, fout, nm, ffb, rel, lock,
        vca, spread, (vp == "" ? "n/a" : sprintf("%.4f", vp)),
        (exc == "" ? "n/a" : sprintf("%+.4f", exc)), settled, cls;
    }' "${CSV}"
} >"${TABLE}"

echo "reexamine: wrote ${TABLE}"
awk -F, '!/^#/ && $1 != "bundle" { c[$16]++ } END { for (k in c) printf "  %-20s %d\n", k, c[k] }' "${TABLE}"
