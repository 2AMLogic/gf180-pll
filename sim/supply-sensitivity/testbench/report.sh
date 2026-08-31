#!/usr/bin/env bash
# gf180-pll :: supply-sensitivity :: metric extraction and record minting
#
# Split out of run.sh so the (long) analysis and the (long) record text do not
# live in the same file as the corner-sweep plumbing.  Invoked by run.sh as
#   report.sh <workdir> <experiment-dir> <testbench-dir>
# and never run on its own: it assumes run.sh has already collected every
# per-run summary row into <workdir>.
#
# Everything below is arithmetic on the collected rows.  No number in the
# record is typed in by hand; the only literals are the acceptance thresholds,
# which run.sh states before the runs and passes through here.

set -euo pipefail
# A campaign may legitimately have run only part of its job sets (the runner's
# SIM_* axis overrides exist for exactly that), so an empty glob must expand to
# nothing rather than to its own pattern.
shopt -s nullglob

WORK="$1"; EXP="$2"; HERE="$3"
ROOT="$(cd "${EXP}/../.." && pwd)"
# shellcheck source=../../lib/simenv.sh
. "${ROOT}/sim/lib/simenv.sh"

# Re-read the constants run.sh declared, by sourcing its assignment block.  The
# alternative -- restating them here -- is how the record's stated criterion and
# the criterion actually applied drift apart.
eval "$(sed -n '/^KFOUT=/,/^ACC_FDEV_PPM=/p;/^CITE_/p;/^VCO_TUNING=/p;/^PASSIVES=/p' "${HERE}/run.sh")"

# The END-plateau escalation's instants are declared by run.sh as OFFSETS from
# t_rend (KD_DEND_TA/_TB/_TSTOP), not as absolute times, because they compose
# with #253's high-plateau escalation -- which moves t_rend.  Re-derive the two
# absolute sets here exactly as run.sh's own dend_at() does, so the record
# states the instants the runner actually used rather than a restatement of
# them.  KD_DEND_* = escalated from the default profile; KD_DENDX_* =
# escalated on top of a high-plateau-escalated profile.
dend_at() { awk -v a="$1" -v b="$2" '
  function s(x) { if (x ~ /[uU]$/) return x * 1e-6;
                  if (x ~ /[nN]$/) return x * 1e-9;
                  if (x ~ /[pP]$/) return x * 1e-12;
                  return x + 0 }
  BEGIN { printf "%.12g", s(a) + s(b) }'; }
KD_DEND_P11="$(dend_at "${KD_TREND_BASE}" "${KD_DEND_TA}")"
KD_DEND_P12="$(dend_at "${KD_TREND_BASE}" "${KD_DEND_TB}")"
KD_DEND_TSTOP_ABS="$(dend_at "${KD_TREND_BASE}" "${KD_DEND_TSTOP}")"
KD_DENDX_P12="$(dend_at "${KD_TREND_X}" "${KD_DEND_TB}")"
KD_DENDX_TSTOP_ABS="$(dend_at "${KD_TREND_X}" "${KD_DEND_TSTOP}")"
# The default END-plateau window's own end instant (t_rend + 1.6 us derived
# form), for the "short" side of the comparison table's prose.
KD_DEND_P12_BASE="$(dend_at "${KD_TSTOP_BASE}" "-1.6u")"

RID="$(simenv_record_id)"
SNAPDIR="${EXP}/netlist-snapshots"; mkdir -p "${SNAPDIR}"
CORNERSDIR="${EXP}/corners/${RID}"; mkdir -p "${CORNERSDIR}"
RECORDSDIR="${EXP}/records";        mkdir -p "${RECORDSDIR}"

# ---------------------------------------------------------------------------
# Frozen DUT snapshots.  Two decks, two snapshots: a record whose claim spans
# two testbenches has to freeze both, or half its numbers are unreproducible.
# ---------------------------------------------------------------------------
cp "${WORK}/dut_lock.sp" "${SNAPDIR}/${RID}.spice"
cp "${WORK}/dut_dyn.sp"  "${SNAPDIR}/${RID}-dyn.spice"
SHA_LOCK="$(simenv_sha256 "${SNAPDIR}/${RID}.spice")"
SHA_DYN="$(simenv_sha256 "${SNAPDIR}/${RID}-dyn.spice")"

# ---------------------------------------------------------------------------
# Archive every raw log as committed evidence.
# ---------------------------------------------------------------------------
for f in "${WORK}"/s100_*.csv; do
  IFS=, read -r bundle temp vdd _ <<<"$(cat "${f}")"
  tag="f100_${bundle}_T${temp}_V${vdd}"; tag="${tag//./p}"; tag="${tag//-/m}"
  simenv_archive_log "${WORK}" "${tag}" "${CORNERSDIR}" \
    "f100_$(simenv_corner_id "${bundle}" "${temp}" "${vdd}")"
done
for f in "${WORK}"/s050_*.csv; do
  IFS=, read -r bundle temp vdd _ <<<"$(cat "${f}")"
  tag="f050_${bundle}_T${temp}_V${vdd}"; tag="${tag//./p}"; tag="${tag//-/m}"
  simenv_archive_log "${WORK}" "${tag}" "${CORNERSDIR}" \
    "f050_$(simenv_corner_id "${bundle}" "${temp}" "${vdd}")"
done
for f in "${WORK}"/s100x_*.csv; do
  IFS=, read -r bundle temp vdd _ <<<"$(cat "${f}")"
  ts="$(cut -d, -f27 <"${f}")"
  tag="f100_${bundle}_T${temp}_V${vdd}_X${ts}"; tag="${tag//./p}"; tag="${tag//-/m}"
  simenv_archive_log "${WORK}" "${tag}" "${CORNERSDIR}" \
    "f100x_$(simenv_corner_id "${bundle}" "${temp}" "${vdd}")"
done
for f in "${WORK}"/s100m_*.csv; do
  IFS=, read -r bundle temp vdd _ <<<"$(cat "${f}")"
  ts="$(cut -d, -f27 <"${f}")"; tm="$(cut -d, -f28 <"${f}")"
  tag="f100_${bundle}_T${temp}_V${vdd}_X${ts}_M${tm}"; tag="${tag//./p}"; tag="${tag//-/m}"
  simenv_archive_log "${WORK}" "${tag}" "${CORNERSDIR}" \
    "f100m_$(simenv_corner_id "${bundle}" "${temp}" "${vdd}")"
done
for f in "${WORK}"/sdyn_*.csv; do
  IFS=, read -r bundle temp _ <<<"$(cat "${f}")"
  tag="dyn_${bundle}_T${temp}"; tag="${tag//./p}"; tag="${tag//-/m}"
  simenv_archive_log "${WORK}" "${tag}" "${CORNERSDIR}" \
    "dyn_$(simenv_corner_id "${bundle}" "${temp}" 3.30)"
  cp "${WORK}/wave_${bundle}_${temp}.csv" \
     "${CORNERSDIR}/supply_transient_$(simenv_corner_id "${bundle}" "${temp}" 3.30).csv"
done
# The criterion-3 high-plateau settling escalation's own runs (#253) -- same
# corner, longer hold, own work directory (the "_X<KD_TRAMP_X>" tag
# --one-dyn's escalated invocation uses) so archiving them is additive.
for f in "${WORK}"/sdynx_*.csv; do
  IFS=, read -r bundle temp _ <<<"$(cat "${f}")"
  tag="dyn_${bundle}_T${temp}_X${KD_TRAMP_X}"; tag="${tag//./p}"; tag="${tag//-/m}"
  simenv_archive_log "${WORK}" "${tag}" "${CORNERSDIR}" \
    "dynx_$(simenv_corner_id "${bundle}" "${temp}" 3.30)"
  cp "${WORK}/wavex_${bundle}_${temp}.csv" \
     "${CORNERSDIR}/supply_transient_$(simenv_corner_id "${bundle}" "${temp}" 3.30)_esc.csv"
done
# The criterion-3 END-plateau settling escalation's own runs (#255) -- same
# corner again, post-ramp hold extended, own work directory again (the
# "_E<p12>" tag, composed on top of the "_X<KD_TRAMP_X>" tag when this corner
# had ALSO been high-plateau escalated -- field 49 of its own row says which,
# so the archive names the directory the runner actually wrote rather than
# guessing at it).
for f in "${WORK}"/sdynend_*.csv; do
  IFS=, read -r bundle temp _ <<<"$(cat "${f}")"
  if [ "$(cut -d, -f49 <"${f}")" = "1" ]; then
    tag="dyn_${bundle}_T${temp}_X${KD_TRAMP_X}_E${KD_DENDX_P12}"
  else
    tag="dyn_${bundle}_T${temp}_E${KD_DEND_P12}"
  fi
  tag="${tag//./p}"; tag="${tag//-/m}"
  simenv_archive_log "${WORK}" "${tag}" "${CORNERSDIR}" \
    "dynend_$(simenv_corner_id "${bundle}" "${temp}" 3.30)"
  cp "${WORK}/waveend_${bundle}_${temp}.csv" \
     "${CORNERSDIR}/supply_transient_$(simenv_corner_id "${bundle}" "${temp}" 3.30)_end.csv"
done

# ---------------------------------------------------------------------------
# Settling escalation: which run of a corner is the one the record reports.
# ---------------------------------------------------------------------------
# A corner may have been simulated up to three times: once at the default
# transient length; once, if its residual frequency error was still over
# threshold there, at the longer length run.sh escalates to; and once more, if
# it is STILL over threshold there, at the finer timestep ceiling of the
# cross-check.  The row that goes into the record is the BEST-RESOLVED run
# available for that corner -- longest transient first, then finest timestep
# ceiling -- because that is the one closest to both a settled and a correctly
# integrated measurement.  The earlier runs are NOT discarded: they are the
# other half of the comparison written to settling_rerun.csv below, which is
# what turns "did not meet the lock criterion" into one of three different
# claims -- "was still converging", "was under-RESOLVED", or "is genuinely
# under-damped at that operating point" -- only the last of which is a
# design-margin finding.
#
# The rank field appended here (0 default, 1 escalated, 2 cross-checked) breaks
# a tie the transient length alone cannot: the cross-check runs at the SAME
# length as the escalation and differs only in the timestep ceiling.
ROWS="${WORK}/.steady_rows.csv"
{ for f in "${WORK}"/s100_*.csv;  do sed 's/$/,0/' "${f}"; done
  for f in "${WORK}"/s100x_*.csv; do sed 's/$/,1/' "${f}"; done
  for f in "${WORK}"/s100m_*.csv; do sed 's/$/,2/' "${f}"; done; } \
  | awk -F, -v dflt="${KTSTOP_BASE}" '
    { k = $1 "|" $2 "|" $3; t = tnum($27 == "" ? dflt : $27); r = $NF + 0;
      line = $0; sub(/,[0-9]+$/, "", line);
      if (!(k in bt) || t > bt[k] || (t == bt[k] && r > br[k])) {
        bt[k] = t; br[k] = r; best[k] = line } }
    END { for (k in best) print best[k] }
    function tnum(s,   v) {
      v = s + 0;
      if (s ~ /[mM]$/) return v * 1e-3;
      if (s ~ /[uU]$/) return v * 1e-6;
      if (s ~ /[nN]$/) return v * 1e-9;
      if (s ~ /[pP]$/) return v * 1e-12;
      return v;
    }' >"${ROWS}"

# ---------------------------------------------------------------------------
# Extracted metrics: the steady-state grid.
# ---------------------------------------------------------------------------
STEADY="${CORNERSDIR}/supply_steady.csv"
{
  simenv_provenance "supply-sensitivity" "${RID}" \
    "design/pll_top.sch -> sim/supply-sensitivity/netlist-snapshots/${RID}.spice" \
    "process{typical,ff,ss,fs,sf} x temp{-40,27,125}C x vdd{2.97,3.30,3.63}V = 45 points at f_out=${KFOUT} Hz, plus 9 points at f_out=${KFOUT2} Hz (typical bundle) for the quiescent/dynamic power split"
  echo "# dut: design/pll_top.sch (#52) -- pfd_cp (#9, post-#24 cp_dumpbuf) +"
  echo "#   loop_filter (#10) + vco (#8) + divider_chain + lock_detector (#11)"
  echo "# band/vctrl0: derived from #8's committed f(Vctrl) table,"
  echo "#   ${VCO_TUNING#"${ROOT}/"}"
  echo "# fdev_ppm: (f_out - f_out at 3.30 V, same bundle/temp) / f_out(3.30 V), ppm"
  echo "# phi_b_s: static REF->FB phase error in the late window, seconds"
  echo "# skew_s: mean UP/DN pulse-WIDTH difference over 3 probes, seconds"
  echo "# p_tot_w: vdd * (|i_core| + |i_vco| + |i_div|)"
  echo "# tstop/tmax: the transient length and internal-timestep ceiling THIS"
  echo "#   row was run at -- per row, not per grid: see the settling escalation"
  echo "#   and the timestep-ceiling cross-check in run.sh"
  echo "bundle,temp_c,vdd_v,band,fout_hz,fdev_ppm,ferr,phi_b_s,skew_s,skew_spread_s,wup_s,wdn_s,nmeas,vctrl_avg_v,vctrl_min_v,vctrl_max_v,lock_lvl_v,i_core_a,i_vco_a,i_div_a,p_tot_w,verdict,tstop,tmax"
  sort -t, -k1,1 -k2,2n -k3,3n "${ROWS}" | awk -F, -v OFS=, \
    -v accf="${ACC_FERR}" -v accp="${ACC_PHI_FRAC}" -v accn="${ACC_NTOL}" \
    -v accl="${ACC_LOCK_FRAC}" -v pwr="${ACC_PWR_MW}" -v dflt_ts="${KTSTOP_BASE}" \
    -v dflt_tm="${KTMAX_BASE}" '
    { rows[NR] = $0; if ($3 + 0 == 3.30) fnom[$1 "|" $2] = $10 }
    END {
      for (i = 1; i <= NR; i++) {
        split(rows[i], f, ",");
        bundle=f[1]; temp=f[2]; vdd=f[3]+0; band=f[5]; fref=f[7]+0; n=f[8]+0;
        fout=f[10]+0; ffb=f[11]+0; nmeas=f[12]+0; ferr=f[13]+0; phib=f[14]+0;
        s1=f[15]+0; s2=f[16]+0; s3=f[17]+0; wup=f[18]+0; wdn=f[19]+0;
        vca=f[20]+0; vcmin=f[21]+0; vcmax=f[22]+0; lock=f[23]+0;
        ic=f[24]+0; iv=f[25]+0; id=f[26]+0;
        ts=(f[27] == "" ? dflt_ts : f[27]);
        tm=(f[28] == "" ? dflt_tm : f[28]);
        fn = fnom[bundle "|" temp];
        dev = (fn > 0) ? (fout - fn) / fn * 1e6 : 0;
        sk = (s1 + s2 + s3) / 3;
        smax = s1; smin = s1;
        if (s2 > smax) smax = s2; if (s2 < smin) smin = s2;
        if (s3 > smax) smax = s3; if (s3 < smin) smin = s3;
        p = vdd * (abs(ic) + abs(iv) + abs(id));
        tref = 1.0 / fref;
        v = "PASS";
        if (abs(ferr) > accf) v = "FAIL:ferr";
        else if (abs(phib) > accp * tref) v = "FAIL:phi";
        else if (abs(nmeas - n) > accn) v = "FAIL:N";
        else if (abs(fout - n * fref) / (n * fref) > accf) v = "FAIL:fout";
        else if (lock < accl * vdd) v = "FAIL:lock";
        else if (p * 1e3 > pwr) v = "FAIL:power";
        printf "%s,%s,%.2f,%s,%.6g,%.4g,%.4g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.4g,%.4g,%.4g,%.4g,%.6g,%.6g,%.6g,%.6g,%s,%s,%s\n",
          bundle, temp, vdd, band, fout, dev, ferr, phib, sk, smax - smin, wup, wdn,
          nmeas, vca, vcmin, vcmax, lock, ic, iv, id, p, v, ts, tm;
      }
    }
    function abs(x) { return x < 0 ? -x : x }'
} >"${STEADY}"

# ---------------------------------------------------------------------------
# Optional generated diff against a prior record's extracted-metrics CSV.
#
#   SIM_COMPARE=<record-id> ./run.sh
#
# #69 has to re-examine this campaign's 9-corner record `20260801-024935-c4fe724`,
# which was taken at a 400 ps internal-timestep ceiling -- above the PFD set
# pulse, i.e. in violation of the bound `sim/README.md` now states -- against a
# re-run at the bound.  "Diff the re-run against the record it may supersede" is
# a comparison a reader has to be able to CHECK rather than take on trust, and
# restating the prior record's numbers by hand in the new record's prose is
# exactly the drift this file's no-hand-typed-numbers rule exists to prevent.
# So the comparison is computed, from the prior record's own committed
# corners/<id>/supply_steady.csv, over the corners the two runs have in common.
#
# The prior CSV is READ, never written: `sim/` is append-only, so the superseded
# record stands unedited.  Absent SIM_COMPARE nothing changes and the record's
# comparison section reads as not claimed.
# shellcheck disable=SC2034
CMP_TABLE=""
# shellcheck disable=SC2034
CMP_SUMMARY=""
CMP_ID="${SIM_COMPARE:-}"
if [ -n "${CMP_ID}" ]; then
  CMP_CSV="${EXP}/corners/${CMP_ID}/supply_steady.csv"
  [ -f "${CMP_CSV}" ] || {
    echo "ERROR: SIM_COMPARE=${CMP_ID} but ${CMP_CSV} does not exist" >&2
    exit 1; }
  # Compared: the verdict, and the three measured quantities that carry it --
  # settled output frequency, and the design's OWN lock-flag level.  The lock
  # flag is included because it is what separates "the loop did not lock" from
  # "the integration did not resolve the phase detector": an f_out ABOVE target
  # with LOCK at ~0 V is feedback running FASTER than the reference while UP is
  # still asserted, which is the artefact signature, not a design result.
  # shellcheck disable=SC2034
  CMP_TABLE="$(awk -F, '
    FNR == 1 { file++ }
    !/^#/ && $1 != "bundle" {
      k = $1 "/" $2 "C/" sprintf("%.2f", $3 + 0) "V";
      if (file == 1) { ov[k]=$22; of[k]=$5+0; ol[k]=$17+0; om[k]=$24; seen[k]=1 }
      else if (k in seen) {
        n++;
        flip = (ov[k] != $22);
        if (flip) nflip++;
        printf "  | %s | %s | %s | **%s** | %.5g | %.5g | %.3g | %.3g | %s |\n",
          k, (om[k] == "" ? "400p" : om[k]), ov[k], $22,
          of[k]/1e6, ($5+0)/1e6, ol[k], $17+0, (flip ? "**yes**" : "no");
      }
    }
    END { printf "@@ %d %d\n", n+0, nflip+0 > "/dev/stderr" }
  ' "${CMP_CSV}" "${STEADY}" 2>"${WORK}/.cmpstat")"
  read -r _ CMP_N CMP_NFLIP <"${WORK}/.cmpstat"
  if [ "${CMP_N}" -eq 0 ]; then
    # "0 of 0 verdicts changed" reads as reassurance and is not one.
    echo "ERROR: SIM_COMPARE=${CMP_ID} shares NO corners with this run -- there" >&2
    echo "       is nothing to diff, and an empty comparison must not be minted" >&2
    echo "       as though it were a clean one." >&2
    exit 1
  elif [ "${CMP_NFLIP}" -gt 0 ]; then
    # shellcheck disable=SC2034
    CMP_SUMMARY="**${CMP_NFLIP} of the ${CMP_N} shared corner(s) change verdict.** The re-run is MATERIALLY different from \`${CMP_ID}\`, so this record supersedes it rather than merely repeating it."
  else
    # shellcheck disable=SC2034
    CMP_SUMMARY="**No verdict changes across the ${CMP_N} shared corner(s).** The measured columns are the evidence for how far the underlying quantities moved; a reader who wants a tolerance judgement should make it from those, not from the verdict column alone."
  fi
fi

# ---------------------------------------------------------------------------
# Extracted metrics: the settling re-run, and its verdict per corner.
# ---------------------------------------------------------------------------
# The question this file answers is the one a bare FAIL row cannot: at a corner
# that did not meet the lock criterion inside the default transient, was the
# loop merely still converging, was it under-RESOLVED, or is it genuinely
# under-damped there?  It is answered by running the SAME corner again -- at
# ~4 loop time constants, and then, if it is still out, at the finer timestep
# ceiling -- and reading four things off those runs:
#
#   - is the loop in lock AT ALL (divide ratio right, absolute output frequency
#     right)?  If not, the corner is not an under-damping finding, it is a
#     lock-range finding, and the two must not be conflated;
#   - has the residual frequency error come inside threshold at the longer
#     length?  If yes, the short run's FAIL was a transient-budget artefact;
#   - if not, does it come inside threshold at the finer TIMESTEP CEILING, same
#     length?  If yes, the failure was an artefact of the INTEGRATION, not of
#     the loop -- PR #64's stepped-over PFD set pulse on this same DUT -- and
#     this campaign is not entitled to call it a design result;
#   - only if the loop IS in lock and the residual is STILL over threshold at
#     3.7 tau AND at the finer ceiling is the corner genuinely under-damped --
#     a design-margin finding, not a measurement gap.
#
# `decay_ratio` = |ferr(long)| / |ferr(short)|.  A single-pole settling at the
# loop's own KTAU predicts exp(-(tb_long - tb_short)/KTAU); the ratio is
# reported next to that prediction so "did not decay" is visible as a number
# rather than as an opinion.
SETTLE_DECAY_EXPECTED="$(awk -v a="${KTB%u}" -v b="${KTB_X%u}" -v tau="${KTAU%u}" \
  'BEGIN{printf "%.4g", exp(-(b-a)/tau)}')"
# The two late windows, in units of the loop's own settling time constant --
# derived, so the record cannot state a multiple the run did not use.
KTA_TAU="$(awk -v a="${KTA%u}" -v tau="${KTAU%u}" 'BEGIN{printf "%.2f", a/tau}')"
KTB_TAU="$(awk -v b="${KTB%u}" -v tau="${KTAU%u}" 'BEGIN{printf "%.2f", b/tau}')"
KTA_X_TAU="$(awk -v a="${KTA_X%u}" -v tau="${KTAU%u}" 'BEGIN{printf "%.2f", a/tau}')"
KTB_X_TAU="$(awk -v b="${KTB_X%u}" -v tau="${KTAU%u}" 'BEGIN{printf "%.2f", b/tau}')"
KTSTOP_X_TAU="$(awk -v s="${KTSTOP_X%u}" -v tau="${KTAU%u}" 'BEGIN{printf "%.2f", s/tau}')"
SETTLE="${CORNERSDIR}/settling_rerun.csv"
{
  simenv_provenance "supply-sensitivity (settling re-run)" "${RID}" \
    "design/pll_top.sch -> sim/supply-sensitivity/netlist-snapshots/${RID}.spice" \
    "every corner whose residual frequency error exceeded ${ACC_FERR} at ${KTSTOP_BASE}, re-run at ${KTSTOP_X}"
  echo "# tstop_short/tstop_long: the two transient lengths, same corner, same"
  echo "#   calibrated warm start, same band -- only the run length differs."
  echo "# decay_ratio: |ferr_long| / |ferr_short|; decay_expected is what a"
  echo "#   single-pole settling at KTAU = ${KTAU} would give between the two"
  echo "#   late windows."
  echo "# tmax_fine/ferr_fine: the timestep-ceiling cross-check -- the SAME"
  echo "#   corner at the SAME tstop_long, re-run at a finer internal timestep"
  echo "#   ceiling.  '--' where the corner settled at tstop_long and no"
  echo "#   cross-check was needed."
  echo "# ferr_best: the residual of the best-resolved run available for the"
  echo "#   corner (longest transient, then finest ceiling) -- the number the"
  echo "#   classification is made from."
  echo "# classification: settles | settles-phi | integration | under-damped | not-locked"
  echo "bundle,temp_c,vdd_v,band,tstop_short,ferr_short,tstop_long,ferr_long,decay_ratio,decay_expected,tmax_fine,ferr_fine,ferr_best,nmeas_best,fout_best_hz,phi_best_s,vctrl_avg_best_v,lock_lvl_best_v,classification"
  for f in "${WORK}"/s100x_*.csv; do
    IFS=, read -r b t v _ <<<"$(cat "${f}")"
    short="${WORK}/s100_${b}_${t}_${v}.csv"
    [ -f "${short}" ] || continue
    fine="${WORK}/s100m_${b}_${t}_${v}.csv"
    if [ -f "${fine}" ]; then paste -d, "${short}" "${f}" "${fine}"
    else                      paste -d, "${short}" "${f}"; fi
  done | awk -F, -v accf="${ACC_FERR}" -v accn="${ACC_NTOL}" \
              -v accp="${ACC_PHI_FRAC}" -v accl="${ACC_LOCK_FRAC}" \
              -v dexp="${SETTLE_DECAY_EXPECTED}" -v NW=28 '
    {
      # `paste` joined two or three summary rows of identical width NW: the
      # default-length run, the escalated run, and -- only where the escalated
      # run was still over threshold -- the timestep-ceiling cross-check.  Every
      # offset below is (block - 1) * NW + field, never a hand-added constant.
      L = NW; F = 2 * NW; nb = int(NF / NW);
      b=$1; t=$2; v=$3+0; band=$5; ts_s=$(27); ts_l=$(L+27);
      fes=abs($13); fel=abs($(L+13));
      # The BEST-resolved run is the cross-check where it exists, else the
      # escalated run.  The classification is made from that block, so a corner
      # is never called under-damped on the strength of the coarser run when a
      # finer one of the same length exists.
      Bo = (nb >= 3 ? F : L);
      tm_f = (nb >= 3 ? $(F+28) : "--");
      fe_f = (nb >= 3 ? sprintf("%.4g", $(F+13)+0) : "--");
      feb  = $(Bo+13)+0;
      fr=$(Bo+7)+0; n=$(Bo+8)+0; fo=$(Bo+10)+0; nm=$(Bo+12)+0; ph=$(Bo+14)+0;
      vca=$(Bo+20)+0; lk=$(Bo+23)+0; tref=1.0/fr;
      locked = (abs(nm - n) <= accn) && (abs(fo - n*fr)/(n*fr) <= accf);
      if (!locked)                       cls = "not-locked";
      else if (abs(feb) > accf)          cls = "under-damped";
      # Inside threshold at the best-resolved run, but NOT at the escalated run
      # of the same length: the only thing that changed is the integration, so
      # that is what the earlier failure was.
      else if (nb >= 3 && fel > accf)    cls = "integration";
      else if (abs(ph) > accp*tref || lk < accl*v) cls = "settles-phi";
      else                               cls = "settles";
      printf "%s,%s,%.2f,%s,%s,%.4g,%s,%.4g,%.4g,%.4g,%s,%s,%.4g,%.6g,%.6g,%.6g,%.4g,%.4g,%s\n",
        b, t, v, band, ts_s, $13+0, ts_l, $(L+13)+0,
        (fes > 0 ? fel/fes : 0), dexp, tm_f, fe_f, feb, nm, fo, ph, vca, lk, cls;
    }
    function abs(x) { return x < 0 ? -x : x }' | sort -t, -k1,1 -k2,2n -k3,3n
} >"${SETTLE}"

# ---------------------------------------------------------------------------
# Extracted metrics: the quiescent/dynamic power split.
# ---------------------------------------------------------------------------
POWER="${CORNERSDIR}/power_split.csv"
{
  simenv_provenance "supply-sensitivity (power split)" "${RID}" \
    "design/pll_top.sch -> sim/supply-sensitivity/netlist-snapshots/${RID}.spice" \
    "typical bundle x temp{-40,27,125}C x vdd{2.97,3.30,3.63}V, each locked at ${KFOUT} Hz and at ${KFOUT2} Hz"
  echo "# I(f) = I_q + k*f fitted per domain through the two locked operating"
  echo "#   points; I_q is the frequency-INDEPENDENT (quiescent) part and"
  echo "#   k*f_out the frequency-PROPORTIONAL (dynamic) part at ${KFOUT} Hz."
  echo "# domains: core = pfd_cp + lock_detector (loop_filter is passive);"
  echo "#   vco = bias + band mirrors + V->I + ring + output buffer;"
  echo "#   div = divider_chain (div-2/3 cells, retiming flop, input inverters)"
  echo "bundle,temp_c,vdd_v,domain,i_at_100mhz_a,i_at_50mhz_a,i_quiescent_a,i_dynamic_a,p_quiescent_w,p_dynamic_w"
  for f in "${WORK}"/s050_*.csv; do
    IFS=, read -r b t v _ <<<"$(cat "${f}")"
    hi="${WORK}/s100_${b}_${t}_${v}.csv"
    [ -f "${hi}" ] || continue
    paste -d, "${hi}" "${f}"
  done | awk -F, -v f1="${KFOUT}" -v f2="${KFOUT2}" '
    {
      b=$1; t=$2; v=$3+0;
      # `paste` joined two summary rows of identical width, so the width is
      # NF/2 and is read off the data rather than restated as a constant.
      NW = int(NF / 2);
      # first row block is the 100 MHz run (fields 1..27), second the 50 MHz
      # run (fields 28..54); domain currents are at offsets 24/25/26 inside
      # each block, i.e. 24/25/26 and 51/52/53.  NW = the summary row width
      # run.sh emits, derived rather than inlined so adding a column to that
      # row (as `tstop` was) cannot silently shift the currents of the second
      # block onto the wrong fields -- which reads vctrl_max and lock_lvl as if
      # they were currents and quietly poisons the whole quiescent/dynamic
      # split.
      split("core vco div", D, " ");
      for (d = 1; d <= 3; d++) {
        i1 = abs($(23 + d)); i2 = abs($(NW + 23 + d));
        k  = (i1 - i2) / (f1 - f2);
        iq = i1 - k * f1;
        idyn = i1 - iq;
        printf "%s,%s,%.2f,%s,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g\n",
          b, t, v, D[d], i1, i2, iq, idyn, v * iq, v * idyn;
      }
    }
    function abs(x) { return x < 0 ? -x : x }' | sort -t, -k2,2n -k3,3n -k4,4
} >"${POWER}"

# ---------------------------------------------------------------------------
# Extracted metrics: the step/ramp runs.
# ---------------------------------------------------------------------------
# supply_dynamic.csv reports the BEST-RESOLVED run of each corner -- the
# criterion-3 escalations' longer-hold re-runs where one exists, else the
# default-hold run -- exactly the same "longest available hold wins" rule
# ROWS applies to the criterion-1 steady-state grid above (#253, #255).  The
# trailing esc_rank/t_hi_end_s and esc_rank_end/t_end_s column PAIRS say, per
# row, which hold each plateau's verdict was measured at: esc_rank 0 = the
# default ${KD_TB_HI} high-plateau window, 1 = escalated to ${KD_TB_HI_X};
# esc_rank_end 0 = the default ${KD_TSTOP_BASE} post-ramp hold, 1 = escalated
# past it.  The earlier (default-hold) rows are not discarded -- they are the
# short side of the comparisons in dyn_settling_rerun.csv and
# dyn_end_settling_rerun.csv below.
#
# The two ranks are SUMMED to order the rows, and that is a total order rather
# than an arbitrary tie-break because run.sh's END escalation is dispatched
# from the best row the high-plateau escalation left behind, not from the
# default row (see its "END-plateau settling escalation" block).  So a corner
# that needed both is re-run ONCE, on the high-plateau-escalated profile with
# the post-ramp hold extended on top, and scores 2 -- strictly above either
# single escalation, and better resolved on BOTH plateaus at once.  A corner
# that needed only one has a single rank-1 row, and no rank-1 row can collide
# with another, because needing both is exactly what produces the rank-2 row
# instead.
DYNROWS="${WORK}/.dyn_rows.csv"
{ for f in "${WORK}"/sdyn_*.csv;    do cat "${f}"; done
  for f in "${WORK}"/sdynx_*.csv;   do cat "${f}"; done
  for f in "${WORK}"/sdynend_*.csv; do cat "${f}"; done; } \
  | awk -F, '
    { k = $1 "|" $2; r = $49 + $51;
      if (!(k in br) || r > br[k]) { br[k] = r; best[k] = $0 } }
    END { for (k in best) print best[k] }' >"${DYNROWS}"

DYNCSV="${CORNERSDIR}/supply_dynamic.csv"
{
  simenv_provenance "supply-sensitivity (step/ramp)" "${RID}" \
    "design/pll_top.sch -> sim/supply-sensitivity/netlist-snapshots/${RID}-dyn.spice" \
    "typical/27C, ss/-40C, ff/125C -- one transient each, carrying a ${KD_LO}->${KD_HI} V step and a ${KD_HI}->${KD_END} V ramp, reported at the best-resolved (longest) high-plateau AND end-plateau hold available per corner (see esc_rank / esc_rank_end)"
  echo "# phi_NN: static REF->FB phase error at probe NN (see the record's"
  echo "#   methodology for the probe instants); phi01/02 pre-step,"
  echo "#   phi03..06 through the step, phi07/08 settled high,"
  echo "#   phi09/10 during the ramp, phi11/12 settled at the low rail."
  echo "# ferr_*: residual fractional frequency error on each settled plateau"
  echo "# lock_*: LOCK-flag average over each phase of the profile, volts"
  echo "# esc_rank: 0 = default ${KD_TB_HI} high-plateau hold, 1 = escalated to"
  echo "#   ${KD_TB_HI_X} (#253) -- see dyn_settling_rerun.csv for the corners"
  echo "#   that escalated and how each resolved."
  echo "# t_hi_end_s: the instant (seconds) the ferr_hi/lock_hi/vc_hi window"
  echo "#   for THIS row actually ended at -- per row, not per campaign."
  echo "# esc_rank_end: 0 = default ${KD_TSTOP_BASE} post-ramp hold, 1 ="
  echo "#   escalated past it (#255) -- see dyn_end_settling_rerun.csv."
  echo "# t_end_s: the instant (seconds) the ferr_end/lock_end/vc_end window"
  echo "#   for THIS row actually ended at (probe p12) -- per row."
  echo "bundle,temp_c,band,vctrl0_v,phi01,phi02,phi03,phi04,phi05,phi06,phi07,phi08,phi09,phi10,phi11,phi12,ferr_lo,ferr_hi,ferr_end,fout_lo,fout_hi,fout_end,fout_step,fout_ramp,vc_lo,vc_hi,vc_end,vc_smax,vc_smin,vc_rmax,vc_rmin,vc_all_max,vc_all_min,lock_lo,lock_stp,lock_hi,lock_rmp,lock_end,lock_min,i_core_lo,i_vco_lo,i_div_lo,i_core_hi,i_vco_hi,i_div_hi,i_core_end,i_vco_end,i_div_end,esc_rank,t_hi_end_s,esc_rank_end,t_end_s"
  sort -t, -k1,1 "${DYNROWS}"
} >"${DYNCSV}"

# ---------------------------------------------------------------------------
# Extracted metrics: the criterion-3 high-plateau settling re-run.
# ---------------------------------------------------------------------------
# Answers, for every corner escalated above, the same question the
# criterion-1 settling re-run answers for the steady-state grid: did the
# longer hold bring ferr_hi inside ${ACC_FERR} (a settling-budget artefact at
# the default hold), or is the corner still over threshold with the loop
# otherwise in lock (a genuine design-margin finding, routed to
# sim/loop-dynamics -- #10)?  A corner whose LOCK flag never recovers on
# EITHER hold is a lock-range finding, not a damping one, and is classified
# separately so the two are not conflated.
DYNSETTLE="${CORNERSDIR}/dyn_settling_rerun.csv"
{
  simenv_provenance "supply-sensitivity (criterion-3 settling re-run)" "${RID}" \
    "design/pll_top.sch -> sim/supply-sensitivity/netlist-snapshots/${RID}-dyn.spice" \
    "every step/ramp corner whose ferr_hi exceeded ${ACC_FERR} at the default ${KD_TB_HI} high-plateau hold, re-run with the hold pushed to ${KD_TB_HI_X}"
  echo "# t_hi_end_short/long: the high-plateau window's end instant, default"
  echo "#   and escalated -- only the hold length differs, same corner, same"
  echo "#   calibrated warm start, same band."
  echo "# classification: resolved (ferr_hi came inside ${ACC_FERR} at the"
  echo "#   longer hold -- a settling-budget artefact, matching the fate of"
  echo "#   every one of criterion 1's apparent failures on this same grid) |"
  echo "#   genuine (still outside ${ACC_FERR} with the loop otherwise in"
  echo "#   lock -- a design-margin finding for sim/loop-dynamics, #10) |"
  echo "#   not-locked (LOCK flag never recovers on the escalated hold either)"
  echo "bundle,temp_c,band,t_hi_end_short,ferr_hi_short,t_hi_end_long,ferr_hi_long,lock_hi_long,vctrl0_v,classification"
  for f in "${WORK}"/sdynx_*.csv; do
    IFS=, read -r b t _ <<<"$(cat "${f}")"
    short="${WORK}/sdyn_${b}_${t}.csv"
    [ -f "${short}" ] || continue
    paste -d, "${short}" "${f}"
  done | awk -F, -v accf="${ACC_FERR}" -v accl="${ACC_LOCK_FRAC}" -v khi="${KD_HI}" '
    # NW = the summary row width run.sh emits, derived from the pasted pair
    # rather than inlined, for the same reason the power split derives it: a
    # column added to that row (as #255 added esc_rank_end/t_end_s) must not
    # silently shift the escalated block onto the wrong fields.
    NR == 1 { NW = int(NF / 2) }
    {
      b=$1; t=$2; band=$3; vc0=$4;
      ts_s=$50; fe_s=abs($18);
      ts_l=$(NW+50); fe_l=abs($(NW+18)); lk_l=$(NW+36)+0;
      # The rail during the high plateau is KD_HI at every corner (the
      # profile, not the row, sets it) -- ACC_LOCK_FRAC is stated as a
      # fraction of the rail, so compare against KD_HI, not vctrl0.
      if (lk_l < accl * khi)        cls = "not-locked";
      else if (fe_l <= accf)        cls = "resolved";
      else                          cls = "genuine";
      printf "%s,%s,%s,%s,%.4g,%s,%.4g,%.4g,%s,%s\n",
        b, t, band, ts_s, fe_s, ts_l, fe_l, lk_l, vc0, cls;
    }
    function abs(x) { return x < 0 ? -x : x }' | sort -t, -k1,1 -k2,2n
} >"${DYNSETTLE}"

# Escalation summary, computed from dyn_settling_rerun.csv the same way the
# criterion-1 escalation summary above is computed from settling_rerun.csv.
eval "$(awk -F, '
  !/^#/ && $1 != "bundle" {
    n++;
    id = $1 "/" $2 "C";
    c = $10;
    if (c == "resolved")        nr++;
    else if (c == "genuine")    { ng++; margin = (margin == "" ? id : margin " " id) }
    else                        { nl++; margin = (margin == "" ? id : margin " " id) }
  }
  END {
    printf "N_DYN_ESC=%d\nN_DYN_RESOLVED=%d\nN_DYN_GENUINE=%d\nN_DYN_NOTLOCK=%d\n",
      n+0, nr+0, ng+0, nl+0;
    printf "DYN_MARGIN_LIST=%s\n", (margin == "" ? "(none)" : "\"" margin "\"");
  }' "${DYNSETTLE}")"

# ---------------------------------------------------------------------------
# Extracted metrics: the criterion-3 END-plateau settling re-run (#255).
# ---------------------------------------------------------------------------
# The same disambiguation one plateau later: a corner whose |ferr_end|
# exceeded ${ACC_FERR} at its default post-ramp hold and was re-run with that
# hold extended either comes inside the criterion there (the short run's FAIL
# was a settling-budget artefact -- `settles`) or does not (`under-damped` --
# a genuine design-margin finding, routed to #10, not absorbed here).
#
# Deliberately a TWO-way classification, unlike the criterion-1 re-run's
# three-way one: #255 scopes the END-plateau escalation to the hold length
# only, and does not re-derive criterion 1's timestep-ceiling cross-check
# tier.  A corner whose LOCK flag is down on the end plateau is already
# reported as such by ferr_end/lock_end in supply_dynamic.csv and by
# criterion 3's own verdict; it is not re-classified here.
#
# The "short" side is the row the escalation was actually dispatched FROM --
# the high-plateau-escalated run where the corner had one, else the
# default-hold run -- so the pair differs in the post-ramp hold and in
# nothing else, which is the only way the decay ratio below means anything.
DYN_END_SETTLE="${CORNERSDIR}/dyn_end_settling_rerun.csv"
{
  simenv_provenance "supply-sensitivity (criterion-3 END-plateau settling re-run)" "${RID}" \
    "design/pll_top.sch -> sim/supply-sensitivity/netlist-snapshots/${RID}-dyn.spice" \
    "every step/ramp corner whose |ferr_end| exceeded ${ACC_FERR} at its default post-ramp hold, re-run with p11/p12 pushed to t_rend + ${KD_DEND_TA}/${KD_DEND_TB} and tstop to t_rend + ${KD_DEND_TSTOP}"
  echo "# t_end_short/t_end_long: the END-plateau window's end instant (probe"
  echo "#   p12, seconds), before and after the escalation -- same corner,"
  echo "#   same profile, same calibrated warm start; only the post-ramp hold"
  echo "#   differs.  On the default profile that is ${KD_DEND_P12_BASE} ->"
  echo "#   ${KD_DEND_P12} s; on a corner that #253 had already escalated it is"
  echo "#   measured from that longer profile's own t_rend instead."
  echo "# decay_ratio: |ferr_end(long)| / |ferr_end(short)|; decay_expected is"
  echo "#   what a single-pole settling at KTAU = ${KTAU} would give between"
  echo "#   those two instants.  A ratio near 1 has not decayed at all; a ratio"
  echo "#   well ABOVE decay_expected settled far more slowly than a single"
  echo "#   pole predicts, which is worth reading even when the row passes."
  echo "# classification: settles | under-damped"
  echo "bundle,temp_c,band,t_end_short,ferr_end_short,t_end_long,ferr_end_long,decay_ratio,decay_expected,classification"
  for f in "${WORK}"/sdynend_*.csv; do
    IFS=, read -r b t _ <<<"$(cat "${f}")"
    short="${WORK}/sdynx_${b}_${t}.csv"
    [ -f "${short}" ] || short="${WORK}/sdyn_${b}_${t}.csv"
    [ -f "${short}" ] || continue
    paste -d, "${short}" "${f}"
  done | awk -F, -v accf="${ACC_FERR}" -v tau="${KTAU%u}" '
    NR == 1 { NW = int(NF / 2) }
    {
      b=$1; t=$2; band=$3;
      ts_s=$52 + 0;          fe_s=abs($19);
      ts_l=$(NW + 52) + 0;   fe_l=abs($(NW + 19));
      # tau is the "9.3u" literal with its suffix stripped, i.e. MICROseconds;
      # ts_* are seconds.  Both terms are put in seconds explicitly rather
      # than left to cancel by luck.
      dexp = exp(-(ts_l - ts_s) / (tau * 1e-6));
      cls = (fe_l > accf) ? "under-damped" : "settles";
      printf "%s,%s,%s,%.6g,%.4g,%.6g,%.4g,%.4g,%.4g,%s\n",
        b, t, band, ts_s, fe_s, ts_l, fe_l, (fe_s > 0 ? fe_l / fe_s : 0), dexp, cls;
    }
    function abs(x) { return x < 0 ? -x : x }' | sort -t, -k1,1 -k2,2n
} >"${DYN_END_SETTLE}"

# END-plateau escalation summary, computed from dyn_end_settling_rerun.csv the
# same way the two summaries above are computed from their own re-run CSVs.
# SLOW_LIST collects the rows that PASSED but decayed markedly slower than a
# single pole would (decay_ratio >= DYN_SLOW_FACTOR x decay_expected): a
# `settles` verdict on such a row is correct but thin, and the record says so
# rather than letting a reader take `settles` for "comfortably settles".
DYN_SLOW_FACTOR=2
eval "$(awk -F, -v accf="${ACC_FERR}" -v slowf="${DYN_SLOW_FACTOR}" '
  !/^#/ && $1 != "bundle" {
    n++;
    id = $1 "/" $2 "C";
    if ($10 == "settles") {
      ns++;
      if ($8 + 0 >= slowf * ($9 + 0)) {
        slow = (slow == "" ? id : slow " " id);
        nslow++;
      }
      m = ($7 + 0) / accf;
      if (wm == "" || m > wm) { wm = m; wmid = id; wmfe = $7; wmdr = $8; wmde = $9 }
    } else {
      nu++; margin = (margin == "" ? id : margin " " id);
      if (worst == "" || $7 + 0 > wf + 0) { wf = $7; worst = id; wband = $3; wdr = $8 }
    }
  }
  END {
    printf "N_DEND=%d\nN_DEND_SETTLES=%d\nN_DEND_UNDAMPED=%d\nN_DEND_SLOW=%d\n",
      n+0, ns+0, nu+0, nslow+0;
    printf "DEND_MARGIN_LIST=%s\n", (margin == "" ? "(none)" : "\"" margin "\"");
    printf "DEND_SLOW_LIST=%s\n",   (slow   == "" ? "(none)" : "\"" slow   "\"");
    printf "DEND_WORST=%s\nDEND_WORST_FERR=%s\nDEND_WORST_BAND=%s\nDEND_WORST_DR=%s\n",
      (worst == "" ? "n/a" : "\"" worst "\""), (worst == "" ? "n/a" : sprintf("%.4g", wf)),
      (worst == "" ? "n/a" : wband), (worst == "" ? "n/a" : sprintf("%.4g", wdr));
    printf "DEND_TIGHT=%s\nDEND_TIGHT_FERR=%s\nDEND_TIGHT_MARGIN=%s\nDEND_TIGHT_DR=%s\nDEND_TIGHT_DEXP=%s\n",
      (wmid == "" ? "n/a" : "\"" wmid "\""), (wmid == "" ? "n/a" : sprintf("%.4g", wmfe)),
      (wmid == "" ? "n/a" : sprintf("%.1f%%", 100 * (1 - wm))),
      (wmid == "" ? "n/a" : sprintf("%.4g", wmdr)), (wmid == "" ? "n/a" : sprintf("%.4g", wmde));
  }' "${DYN_END_SETTLE}")"
: "${N_DEND:=0}"; : "${N_DEND_SETTLES:=0}"; : "${N_DEND_UNDAMPED:=0}"; : "${N_DEND_SLOW:=0}"
: "${DEND_MARGIN_LIST:=(none)}"; : "${DEND_SLOW_LIST:=(none)}"
: "${DEND_WORST:=n/a}"; : "${DEND_WORST_FERR:=n/a}"; : "${DEND_WORST_BAND:=n/a}"; : "${DEND_WORST_DR:=n/a}"
: "${DEND_TIGHT:=n/a}"; : "${DEND_TIGHT_FERR:=n/a}"; : "${DEND_TIGHT_MARGIN:=n/a}"
: "${DEND_TIGHT_DR:=n/a}"; : "${DEND_TIGHT_DEXP:=n/a}"

# ---------------------------------------------------------------------------
# Headline scalars for the record.
# ---------------------------------------------------------------------------
eval "$(awk -F, -v accv_lo="${ACC_VCTRL_LO}" -v accv_hi="${ACC_VCTRL_HI}" -v pwr="${ACC_PWR_MW}" '
  !/^#/ && $1 != "bundle" {
    n++;
    bundle=$1; temp=$2; vdd=$3+0; fout=$5+0; dev=$6+0; ferr=$7+0; phib=$8+0;
    sk=$9+0; spread=$10+0; vca=$14+0; vcmin=$15+0; vcmax=$16+0; p=$21+0; v=$22;
    id = bundle "/" temp "C/" sprintf("%.2f", vdd) "V";
    if (v != "PASS") { nfail++; if (faillist == "") faillist = id "(" v ")"; else faillist = faillist " " id "(" v ")" }
    # Per-class failure tallies.  "N of 45 failed" is not an actionable
    # statement: a residual-frequency miss, a static-phase miss and a
    # lock-DETECTOR miss are three different findings owned by three different
    # design issues, and the record routes each rather than summing them.
    if (v == "FAIL:ferr")  nfferr++;
    if (v == "FAIL:phi")   { nfphi++;  phlist  = (phlist  == "" ? id : phlist  " " id) }
    if (v == "FAIL:lock")  { nflock++; lklist  = (lklist  == "" ? id : lklist  " " id) }
    if (v == "FAIL:N" || v == "FAIL:fout") { nfrange++; rglist = (rglist == "" ? id "(" v ")" : rglist " " id "(" v ")") }
    if (abs(dev) > abs(wdev)) { wdev = dev; wdevid = id }
    if (abs(ferr) > abs(wferr)) { wferr = ferr; wferrid = id }
    if (!seenphi || abs(phib) > abs(wphi)) { wphi = phib; wphiid = id; seenphi = 1 }
    if (!seensk || sk > mxsk) { mxsk = sk; mxskid = id }
    if (!seensk || sk < mnsk) { mnsk = sk; mnskid = id }
    seensk = 1;
    if (spread > wspread) { wspread = spread; wspreadid = id }
    if (p > mxp) { mxp = p; mxpid = id }
    if (!seenp || p < mnp) { mnp = p; mnpid = id }
    seenp = 1;
    if (p * 1e3 > pwr) npfail++;
    if (vcmin < accv_lo || vcmax > accv_hi) { nvout++; if (vout == "") vout = id; else vout = vout " " id }
    if (!seenv || vca > mxvc) { mxvc = vca; mxvcid = id }
    if (!seenv || vca < mnvc) { mnvc = vca; mnvcid = id }
    seenv = 1;
    # dVctrl/dVdd, per (bundle,temp), from the 2.97 and 3.63 V rows
    key = bundle "|" temp;
    if (vdd > 3.6) { vhi[key] = vca; fhi[key] = fout }
    if (vdd < 3.0) { vlo[key] = vca; flo[key] = fout }
  }
  END {
    for (k in vhi) if (k in vlo) {
      s = (vhi[k] - vlo[k]) / (3.63 - 2.97);
      split(k, a, "|");
      if (!seens || s > mxs) { mxs = s; mxsid = a[1] "/" a[2] "C" }
      if (!seens || s < mns) { mns = s; mnsid = a[1] "/" a[2] "C" }
      sum += s; ns++; seens = 1;
    }
    printf "N_STEADY=%d\nN_FAIL=%d\nFAILLIST=%s\n", n, nfail+0, (faillist == "" ? "(none)" : "\"" faillist "\"");
    printf "N_F_FERR=%d\nN_F_PHI=%d\nN_F_LOCK=%d\nN_F_RANGE=%d\n", nfferr+0, nfphi+0, nflock+0, nfrange+0;
    printf "PHI_LIST=%s\nLOCK_LIST=%s\nRANGE_LIST=%s\n",
      (phlist == "" ? "(none)" : "\"" phlist "\""),
      (lklist == "" ? "(none)" : "\"" lklist "\""),
      (rglist == "" ? "(none)" : "\"" rglist "\"");
    printf "WDEV_PPM=%.4g\nWDEV_ID=\"%s\"\n", wdev, wdevid;
    printf "WFERR=%.4g\nWFERR_ID=\"%s\"\n", wferr, wferrid;
    printf "WPHI_NS=%.4g\nWPHI_ID=\"%s\"\n", wphi*1e9, wphiid;
    printf "MXSK_NS=%.4g\nMXSK_ID=\"%s\"\nMNSK_NS=%.4g\nMNSK_ID=\"%s\"\n", mxsk*1e9, mxskid, mnsk*1e9, mnskid;
    printf "WSPREAD_NS=%.4g\nWSPREAD_ID=\"%s\"\n", wspread*1e9, wspreadid;
    printf "MXP_MW=%.4g\nMXP_ID=\"%s\"\nMNP_MW=%.4g\nMNP_ID=\"%s\"\nN_PFAIL=%d\n", mxp*1e3, mxpid, mnp*1e3, mnpid, npfail+0;
    printf "N_VOUT=%d\nVOUT=%s\n", nvout+0, (vout == "" ? "(none)" : "\"" vout "\"");
    printf "MXVC=%.4g\nMXVC_ID=\"%s\"\nMNVC=%.4g\nMNVC_ID=\"%s\"\n", mxvc, mxvcid, mnvc, mnvcid;
    printf "MXSLOPE=%.4g\nMXSLOPE_ID=\"%s\"\nMNSLOPE=%.4g\nMNSLOPE_ID=\"%s\"\nAVSLOPE=%.4g\n", mxs, mxsid, mns, mnsid, sum/ns;
  }
  function abs(x) { return x < 0 ? -x : x }' "${STEADY}")"

# Settling re-run: how many corners were escalated, and how each resolved.
eval "$(awk -F, '
  !/^#/ && $1 != "bundle" {
    n++;
    id = $1 "/" $2 "C/" sprintf("%.2f", $3) "V";
    c = $19;
    if (c == "settles")      ns++;
    else if (c == "settles-phi") np++;
    else if (c == "integration") { ni++; integ = (integ == "" ? id : integ " " id) }
    else if (c == "under-damped") { nu++; margin = (margin == "" ? id : margin " " id) }
    else                     { nl++; margin = (margin == "" ? id : margin " " id) }
    if (c == "under-damped" || c == "not-locked") {
      if (worst == "" || abs($13) > abs(wf)) { wf = $13; worst = id; wband = $4; wdr = $9 }
    }
  }
  END {
    printf "N_RERUN=%d\nN_R_SETTLES=%d\nN_R_PHI=%d\nN_R_UNDAMPED=%d\nN_R_NOTLOCK=%d\nN_R_INTEG=%d\n",
      n+0, ns+0, np+0, nu+0, nl+0, ni+0;
    printf "INTEG_LIST=%s\n", (integ == "" ? "(none)" : "\"" integ "\"");
    printf "MARGIN_LIST=%s\n", (margin == "" ? "(none)" : "\"" margin "\"");
    printf "MARGIN_WORST=%s\nMARGIN_WORST_FERR=%s\nMARGIN_WORST_BAND=%s\nMARGIN_WORST_DR=%s\n",
      (worst == "" ? "n/a" : "\"" worst "\""), (worst == "" ? "n/a" : sprintf("%.4g", wf)),
      (worst == "" ? "n/a" : wband), (worst == "" ? "n/a" : sprintf("%.4g", wdr));
  }
  function abs(x) { return x < 0 ? -x : x }' "${SETTLE}")"

SETTLE_TABLE="$(awk -F, '
  !/^#/ && $1 != "bundle" {
    printf "  | %s | %s | %.2f | %s | %s | %.4g | %s | %.4g | %.3g | %s | %s | %s |\n",
      $1, $2, $3, $4, $5, $6, $7, $8, $9, $11, $12, $19;
  }' "${SETTLE}")"

# Power split totals at the nominal corner and worst corner of the reduced grid.
eval "$(awk -F, '
  !/^#/ && $1 != "bundle" {
    key = $1 "|" $2 "|" $3;
    q[key] += $9; d[key] += $10;
    if ($4 == "core") { qc[key] = $9; dc[key] = $10 }
    if ($4 == "vco")  { qv[key] = $9; dv[key] = $10 }
    if ($4 == "div")  { qd[key] = $9; dd[key] = $10 }
  }
  END {
    for (k in q) {
      split(k, a, "|");
      tot = q[k] + d[k];
      if (tot > mx) { mx = tot; mxid = a[1] "/" a[2] "C/" a[3] "V"; mxq = q[k]; mxd = d[k] }
      if (a[2] == "27" && a[3] + 0 == 3.30) { nq = q[k]; nd = d[k];
        nqc = qc[k]; ndc = dc[k]; nqv = qv[k]; ndv = dv[k]; nqd = qd[k]; ndd = dd[k] }
    }
    printf "SPLIT_MAX_MW=%.4g\nSPLIT_MAX_ID=\"%s\"\nSPLIT_MAXQ_MW=%.4g\nSPLIT_MAXD_MW=%.4g\n", mx*1e3, mxid, mxq*1e3, mxd*1e3;
    printf "NOMQ_MW=%.4g\nNOMD_MW=%.4g\n", nq*1e3, nd*1e3;
    printf "NOMQC_MW=%.4g\nNOMDC_MW=%.4g\nNOMQV_MW=%.4g\nNOMDV_MW=%.4g\nNOMQD_MW=%.4g\nNOMDD_MW=%.4g\n",
      nqc*1e3, ndc*1e3, nqv*1e3, ndv*1e3, nqd*1e3, ndd*1e3;
  }' "${POWER}")"

: "${N_DYN:=0}"; : "${DYN_LOST:=0}"
: "${DYN_PSTEP_NS:=n/a}"; : "${DYN_PSTEP_ID:=n/a}"
: "${DYN_PRAMP_NS:=n/a}"; : "${DYN_PRAMP_ID:=n/a}"
: "${DYN_MXFE:=n/a}"; : "${DYN_MXFE_ID:=n/a}"
: "${DYN_MNLOCK:=n/a}"; : "${DYN_MNLOCK_ID:=n/a}"
: "${DYN_DSTEP_HZ:=n/a}"; : "${DYN_DSTEP_ID:=n/a}"
: "${DYN_DVC:=n/a}"; : "${DYN_DVC_ID:=n/a}"
: "${DYN_VEX:=n/a}"; : "${DYN_VEX_ID:=n/a}"

# Defaults, so a partially-collected campaign still mints an honest record
# instead of dying on an unset variable.  Every one of these is overwritten
# below when the corresponding runs exist; where they survive, the record says
# in as many words that the measurement was not made.
: "${SPLIT_MAX_MW:=n/a}"; : "${SPLIT_MAX_ID:=n/a}"
: "${SPLIT_MAXQ_MW:=n/a}"; : "${SPLIT_MAXD_MW:=n/a}"
: "${NOMQ_MW:=n/a}"; : "${NOMD_MW:=n/a}"
: "${NOMQC_MW:=n/a}"; : "${NOMDC_MW:=n/a}"
: "${NOMQV_MW:=n/a}"; : "${NOMDV_MW:=n/a}"
: "${NOMQD_MW:=n/a}"; : "${NOMDD_MW:=n/a}"
: "${N_RERUN:=0}"; : "${N_R_SETTLES:=0}"; : "${N_R_PHI:=0}"
: "${N_R_UNDAMPED:=0}"; : "${N_R_NOTLOCK:=0}"; : "${MARGIN_LIST:=(none)}"
: "${N_R_INTEG:=0}"; : "${INTEG_LIST:=(none)}"
: "${N_F_FERR:=0}"; : "${N_F_PHI:=0}"; : "${N_F_LOCK:=0}"; : "${N_F_RANGE:=0}"
: "${PHI_LIST:=(none)}"; : "${LOCK_LIST:=(none)}"; : "${RANGE_LIST:=(none)}"
: "${MARGIN_WORST:=n/a}"; : "${MARGIN_WORST_FERR:=n/a}"
: "${MARGIN_WORST_BAND:=n/a}"; : "${MARGIN_WORST_DR:=n/a}"
[ -n "${SETTLE_TABLE}" ] || SETTLE_TABLE="  | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- |"
N_MARGIN=$(( N_R_UNDAMPED + N_R_NOTLOCK ))
# Corners still failing the residual-frequency check in the reported (longest
# available) row, and how many of those the escalation never reached -- because
# it was disabled or capped.  An unescalated ferr failure is an OPEN question,
# not a design result, and the record has to be able to say so.
N_FERRFAIL=$(awk -F, '!/^#/ && $1 != "bundle" && $22 == "FAIL:ferr"' "${STEADY}" | wc -l | tr -d ' ')
N_UNRESOLVED=$(( N_FERRFAIL - N_MARGIN ))
[ "${N_UNRESOLVED}" -ge 0 ] || N_UNRESOLVED=0

# The settling paragraph, and the design-margin finding if there is one.  Both
# are derived from the classification column of settling_rerun.csv, so the
# record cannot report "just needed a longer run" at a corner where the longer
# run says otherwise -- which is the specific way a real margin failure gets
# absorbed into a campaign record as one more data point.
if [ "${N_RERUN}" -eq 0 ] && [ "${N_FERRFAIL}" -eq 0 ]; then
  SETTLE_PROSE="  **No corner needed one.** Every point on this grid met the
  residual-frequency threshold (${ACC_FERR}) inside the default ${KTSTOP_BASE}
  transient, so the runner escalated nothing and the budget-artefact question
  does not arise here."
  V_SETTLE="N/A -- no corner needed one"
elif [ "${N_RERUN}" -eq 0 ]; then
  SETTLE_PROSE="  **NOT RESOLVED -- the escalation did not run.** ${N_FERRFAIL}
  corner(s) missed the residual-frequency threshold (${ACC_FERR}) at
  ${KTSTOP_BASE} and none of them was re-run longer (\`SIM_EXTEND=off\`, or the
  \`SIM_EXTEND_MAX\` budget cap). **This record therefore does not say whether
  those corners are transient-budget artefacts or genuinely under-damped**, and
  their rows must not be read as either. Stated as the open question it is."
  V_SETTLE="**NOT RESOLVED** -- ${N_FERRFAIL} corner(s) never escalated"
else
  SETTLE_PROSE="  | Bundle | Temp | Vdd | Band | tstop (short) | ferr (short) | tstop (long) | ferr (long) | decay ratio | tmax (fine) | ferr (fine) | resolution |
  |---|---|---|---|---|---|---|---|---|---|---|---|
${SETTLE_TABLE}

  Resolution key: \`settles\` = in lock and inside the residual-frequency
  threshold once given the longer run, i.e. the short run's FAIL was a
  transient-budget artefact; \`settles-phi\` = the residual frequency error
  settled but the STATIC phase error (or the block's own LOCK flag) is still
  over threshold, which is a static-offset result, not a settling one;
  \`integration\` = still over threshold at the longer length under the ceiling
  the grid was run at, but inside it at the SAME length under the shared
  closed-loop bound -- so the failure was the simulator's, not the loop's, and
  it is **not** a design result (PR #64 measured exactly this failure mode on
  this DUT: ngspice stepping over \`design/edgedet.sch\`'s 0.33-0.39 ns internal
  PFD set pulse).  This can only arise on a run deliberately taken off the bound
  with \`SIM_TMAX\`; at the bound the class is empty by construction;
  \`under-damped\` = in lock (divide ratio and absolute output frequency both
  correct) but the residual frequency error is STILL over threshold at
  ${KTB_X} = ${KTB_X_TAU} tau **and** at the finer ceiling, i.e. genuinely
  marginal damping at that operating point; \`not-locked\` = the divide ratio or
  the absolute output frequency is wrong at the best-resolved run, so the loop
  is not in lock at that corner at all and the finding is one of lock range,
  not of damping.

  \`decay ratio\` is |ferr(long)| / |ferr(short)|. A loop settling as a single
  pole at KTAU = ${KTAU} would show ${SETTLE_DECAY_EXPECTED} between these two
  late windows; a corner whose ratio is near 1 has not decayed at all, which is
  the numerical form of \"not merely slow\".

  \`tmax (fine)\` / \`ferr (fine)\` are the timestep-ceiling cross-check: the
  same corner, the same ${KTSTOP_X} transient, the same warm start, re-run with
  the internal timestep ceiling at the shared bound ${KTMAX_X}. \`--\` means no
  cross-check was needed -- either the corner came inside the criterion at the
  longer length, or the grid already ran at the bound and there is nothing to
  cross-check against.

  - ${N_RERUN} corner(s) escalated from ${KTSTOP_BASE} to ${KTSTOP_X}
    (${KTSTOP_X_TAU} tau, late window at ${KTA_X_TAU}/${KTB_X_TAU} tau against
    ${KTA_TAU}/${KTB_TAU} tau at the default length).
  - **\`settles\`: ${N_R_SETTLES} corner(s)** -- pass once given enough time,
    i.e. budget artefacts of the short run, not design results.
  - \`settles-phi\`: ${N_R_PHI} corner(s) -- settled in frequency but outside
    the static-phase or LOCK-flag part of the criterion.
  - **\`integration\`: ${N_R_INTEG} corner(s)** -- ${INTEG_LIST}. Not design
    results either: they pass at the same transient length once the timestep
    ceiling resolves the PFD's internal set pulse. Their presence is also the
    measurement that says the ceiling this grid was run at is not sufficient
    everywhere on it, which is a finding about this campaign's own numerics and
    is stated as one.
  - **\`under-damped\`: ${N_R_UNDAMPED} corner(s)**; **\`not-locked\`:
    ${N_R_NOTLOCK} corner(s)** -- still outside the criterion at the longer
    length AND at the finer timestep ceiling.$(
    if [ "${N_UNRESOLVED}" -gt 0 ]; then printf '
  - **%s further corner(s) still fail the residual-frequency check and were
    NOT escalated** (the `SIM_EXTEND_MAX` budget cap). Those rows are
    unresolved: this record does not classify them either way.' "${N_UNRESOLVED}"; fi)"
  if [ "${N_MARGIN}" -eq 0 ] && [ "${N_UNRESOLVED}" -eq 0 ]; then
    V_SETTLE="resolved: ${N_RERUN} of ${N_RERUN} were artefacts (${N_R_INTEG} of the integration, the rest of the transient budget)"
  elif [ "${N_MARGIN}" -eq 0 ]; then
    V_SETTLE="${N_RERUN} escalated, all artefacts (${N_R_INTEG} of the integration); **${N_UNRESOLVED} corner(s) unresolved**"
  else
    V_SETTLE="**${N_MARGIN} genuine design-margin corner(s)** of ${N_RERUN} escalated (${N_R_INTEG} were integration artefacts)"
  fi
fi

if [ "${N_MARGIN}" -eq 0 ] && [ "${N_FERRFAIL}" -eq 0 ]; then
  MARGIN_NOTE="  **No corner on this grid is a design-margin finding.** Every corner that
  missed the lock criterion at the default transient length was re-run at
  ${KTSTOP_X}, and every corner still outside it there was re-run again at the
  ${KTMAX_X} timestep ceiling; all of them came inside the criterion. So the
  short run's failures were artefacts of the transient budget or of the
  integration, and there is nothing here to route back to #10 (loop dynamics)
  or #8 (VCO). That is a conclusion this record is entitled to only because
  both re-runs were made: it is not an assumption."
elif [ "${N_MARGIN}" -eq 0 ]; then
  MARGIN_NOTE="  **No corner is SHOWN to be a design-margin finding, and that is weaker than
  saying none is.** Every corner the escalation reached settled inside the
  criterion at ${KTSTOP_X}; ${N_UNRESOLVED} corner(s) it did not reach are
  still failing the residual-frequency check at ${KTSTOP_BASE} and remain
  unclassified. Nothing is routed back to #10 (loop dynamics) or #8 (VCO) on
  this evidence, but nothing is cleared either."
else
  MARGIN_NOTE="  **DESIGN-MARGIN FINDING -- flagged back, not absorbed.** ${N_MARGIN} corner(s)
  do **not** meet the lock criterion when run to ${KTSTOP_X}
  (${KTSTOP_X_TAU} loop time constants, late window at
  ${KTA_X_TAU}/${KTB_X_TAU} tau) **and do not meet it at the ${KTMAX_X}
  timestep ceiling either**: ${MARGIN_LIST}. At those corners the failure is
  **not** a limit of this record's transient budget and **not** an artefact of
  its integration, and must not be read as either -- the loop had four time
  constants and a ceiling PR #64 showed sufficient to resolve the PFD's
  internal set pulse on this DUT, and still did not settle. Worst of them is
  ${MARGIN_WORST} (band ${MARGIN_WORST_BAND}, residual frequency error
  ${MARGIN_WORST_FERR} at the best-resolved run, decay ratio
  ${MARGIN_WORST_DR} against the ${SETTLE_DECAY_EXPECTED} a single-pole
  settling would give).

  This is consistent with, and is evidence for, \`sim/loop-dynamics\` (#10)'s
  phase-margin-vs-loop-gain result: phase margin falls as \`Icp*Kvco/N\` rises,
  and the affected corners are the high-Kvco operating points of this grid.
  **It is a property of the loop filter / loop gain at those operating points,
  which is #10's claim, and of the VCO gain that sets them, which is #8's** --
  not of this campaign's measurement. Per this repo's convention that deltas
  and failures get flagged back rather than papered over, it is raised against
  #10 (loop-dynamics / loop-filter margin) and #8 (VCO Kvco per band) rather
  than being recorded here as one more FAIL row. This campaign does not propose
  a fix; sizing the loop filter or the Icp trim against the worst-case Kvco is
  #10's decision to make with its own evidence."
fi

# Step/ramp verdicts.
eval "$(awk -F, -v accf="${ACC_FERR}" -v accl="${ACC_LOCK_FRAC}" -v fref="${KFREF}" -v n="${KN}" '
  !/^#/ && $1 != "bundle" {
    nr++;
    id = $1 "/" $2 "C";
    tref = 1.0 / fref;
    # peak |phase| excursion through the step (probes 3..6) and the ramp (9,10)
    pstep = 0; for (i = 7; i <= 10; i++) if (abs($i) > pstep) pstep = abs($i);
    pramp = 0; for (i = 13; i <= 14; i++) if (abs($i) > pramp) pramp = abs($i);
    base = abs($5);
    if (pstep > mxstep) { mxstep = pstep; mxstepid = id }
    if (pramp > mxramp) { mxramp = pramp; mxrampid = id }
    fl = abs($17); fh = abs($18); fe = abs($19);
    if (fl > mxfe) { mxfe = fl; mxfeid = id "(low)" }
    if (fh > mxfe) { mxfe = fh; mxfeid = id "(high)" }
    if (fe > mxfe) { mxfe = fe; mxfeid = id "(end)" }
    lm = $39 + 0;
    if (!seen || lm < mnlock) { mnlock = lm; mnlockid = id } seen = 1;
    dstep = abs($23 - $20);   # |f_out during the step - f_out on the low plateau|
    if (dstep > mxdstep) { mxdstep = dstep; mxdstepid = id }
    dvc = abs($27 - $25);     # |Vctrl(end, 2.97V) - Vctrl(hi, 3.63V)|
    if (dvc > mxdvc) { mxdvc = dvc; mxdvcid = id }
    vex = abs($28 - $25); if (abs($29 - $25) > vex) vex = abs($29 - $25);
    if (vex > mxvex) { mxvex = vex; mxvexid = id }
    if (fl > accf || fh > accf || fe > accf) nlost++;
  }
  END {
    printf "N_DYN=%d\nDYN_LOST=%d\n", nr, nlost+0;
    printf "DYN_PSTEP_NS=%.4g\nDYN_PSTEP_ID=\"%s\"\nDYN_PRAMP_NS=%.4g\nDYN_PRAMP_ID=\"%s\"\n", mxstep*1e9, mxstepid, mxramp*1e9, mxrampid;
    printf "DYN_MXFE=%.4g\nDYN_MXFE_ID=\"%s\"\n", mxfe, mxfeid;
    printf "DYN_MNLOCK=%.4g\nDYN_MNLOCK_ID=\"%s\"\n", mnlock, mnlockid;
    printf "DYN_DSTEP_HZ=%.4g\nDYN_DSTEP_ID=\"%s\"\n", mxdstep, mxdstepid;
    printf "DYN_DVC=%.4g\nDYN_DVC_ID=\"%s\"\nDYN_VEX=%.4g\nDYN_VEX_ID=\"%s\"\n", mxdvc, mxdvcid, mxvex, mxvexid;
  }
  function abs(x) { return x < 0 ? -x : x }' "${DYNCSV}")"

# What was ACTUALLY swept, derived from the collected rows -- never from the
# runner's defaults.  A reduced run must not be able to describe itself as a
# full one, and the only way to guarantee that is to read the description off
# the data.
GRID_BUNDLES_RUN="$(awk -F, '!/^#/ && $1 != "bundle" {print $1}' "${STEADY}" | sort -u | tr '\n' ' ' | sed 's/ $//')"
GRID_TEMPS_RUN="$(awk -F, '!/^#/ && $1 != "bundle" {print $2}' "${STEADY}" | sort -un | tr '\n' ' ' | sed 's/ $//')"
GRID_VDDS_RUN="$(awk -F, '!/^#/ && $1 != "bundle" {printf "%.2f\n", $3}' "${STEADY}" | sort -un | tr '\n' ' ' | sed 's/ $//')"
NB_RUN=$(printf '%s\n' ${GRID_BUNDLES_RUN} | wc -l | tr -d ' ')
NT_RUN=$(printf '%s\n' ${GRID_TEMPS_RUN} | wc -l | tr -d ' ')
NV_RUN=$(printf '%s\n' ${GRID_VDDS_RUN} | wc -l | tr -d ' ')
N_SPLIT=$(awk -F, '!/^#/ && $1 != "bundle"' "${POWER}" | wc -l | tr -d ' ')
N_SPLIT=$(( N_SPLIT / 3 ))
if [ "${N_STEADY}" -eq 45 ]; then
  GRID_STATEMENT="**the full 45-point default grid** \`sim/README.md\` prescribes"
  GRID_JUSTIFY=""
else
  GRID_STATEMENT="**a ${N_STEADY}-point SUBSET of the 45-point default grid**"
  GRID_JUSTIFY="yes"
fi

N_SETTLED=$(( N_STEADY - N_FAIL ))
N_UNSETTLED=${N_FAIL}

# Overall verdicts.  Computed BEFORE the prose blocks below, because those
# blocks interpolate them -- an ordering the campaign's first full-coverage run
# discovered the hard way (with no step/ramp run, the branch that reads V_DYN
# was never taken, so the unbound variable stayed invisible until a run that
# actually measured criterion 3).
V_FREQ=$([ "${N_FAIL}" -eq 0 ] && echo PASS || echo FAIL)
V_PWR=$([ "${N_PFAIL}" -eq 0 ] && echo PASS || echo FAIL)
if [ "${N_DYN:-0}" -eq 0 ]; then V_DYN="NOT MEASURED"; else
  V_DYN=$([ "${DYN_LOST}" -eq 0 ] && echo PASS || echo FAIL); fi
V_VCTRL=$([ "${N_VOUT}" -eq 0 ] && echo PASS || echo "FAIL")

# Criterion-3 escalation verdict (#253) -- mirrors V_SETTLE's three-way
# outcome for criterion 1: nothing needed escalating, everything that
# escalated turned out to be a settling-budget artefact, or at least one
# corner is a genuine design-margin finding.
if [ "${N_DYN_ESC:-0}" -eq 0 ]; then
  V_DYN_SETTLE="N/A -- no criterion-3 corner needed one"
elif [ "${N_DYN_GENUINE:-0}" -eq 0 ] && [ "${N_DYN_NOTLOCK:-0}" -eq 0 ]; then
  V_DYN_SETTLE="resolved: ${N_DYN_ESC} of ${N_DYN_ESC} were settling-budget artefacts"
else
  V_DYN_SETTLE="**${N_DYN_GENUINE} genuine design-margin corner(s)** of ${N_DYN_ESC} escalated (routed to sim/loop-dynamics, #10)"
fi

# Criterion-3 END-plateau escalation verdict (#255) -- the same three outcomes
# for the post-RAMP hold.  N_DENDFAIL/N_DENDUNRESOLVED mirror
# N_FERRFAIL/N_UNRESOLVED for criterion 1: corners still failing ferr_end in
# the best-resolved row, and how many of those the escalation never reached
# (disabled, or the SIM_DYN_END_MAX budget cap), which is a DIFFERENT claim
# from "escalated and still failed" and must not be folded into it.
N_DENDFAIL=$(awk -F, -v accf="${ACC_FERR}" '!/^#/ && $1 != "bundle" { fe = $19 + 0; if (fe < 0) fe = -fe; if (fe > accf) print }' "${DYNCSV}" | wc -l | tr -d ' ')
N_DENDUNRESOLVED=$(( N_DENDFAIL - N_DEND_UNDAMPED ))
[ "${N_DENDUNRESOLVED}" -ge 0 ] || N_DENDUNRESOLVED=0
if [ "${N_DYN:-0}" -eq 0 ]; then
  V_DEND="N/A -- criterion 3 not measured"
elif [ "${N_DEND}" -eq 0 ] && [ "${N_DENDFAIL}" -eq 0 ]; then
  V_DEND="N/A -- no corner needed one"
elif [ "${N_DEND}" -eq 0 ]; then
  V_DEND="**NOT RESOLVED** -- ${N_DENDFAIL} corner(s) never escalated"
elif [ "${N_DEND_UNDAMPED}" -eq 0 ] && [ "${N_DENDUNRESOLVED}" -eq 0 ]; then
  V_DEND="resolved: ${N_DEND} of ${N_DEND} were settling-budget artefacts"
elif [ "${N_DEND_UNDAMPED}" -eq 0 ]; then
  V_DEND="${N_DEND} escalated, all artefacts; **${N_DENDUNRESOLVED} corner(s) unresolved**"
else
  V_DEND="**${N_DEND_UNDAMPED} genuine design-margin corner(s)** of ${N_DEND} escalated (routed to sim/loop-dynamics, #10)"
fi

if [ "${N_DYN}" -eq 0 ]; then
  DYN_BULLETS="  - **Overall criterion 3: NOT MEASURED.** The step/ramp deck
    (\`tb_supply_dyn.sp\`) is implemented, parameterised and exercised -- the
    profile above is the one it runs and the runner builds its job set from
    \`SIM_DYN_PICKS\` -- but **no step/ramp run completed inside this record's
    compute budget**, so this record reports **no** number for the supply-step
    or supply-ramp disturbance and **does not** claim the loop stays locked
    through either. That criterion of #14 is undischarged and the follow-up
    issue carries it. Reporting it as anything other than not-measured would be
    the failure mode \`sim/README.md\` names: a number without a run behind it."
else
  DYN_BULLETS="  - Worst peak REF->FB phase excursion through the **step**:
    **${DYN_PSTEP_NS} ns** at ${DYN_PSTEP_ID}.
  - Worst peak excursion through the **ramp**: **${DYN_PRAMP_NS} ns** at
    ${DYN_PRAMP_ID}.
  - Worst output-frequency excursion measured inside the step disturbance
    (20 CLK cycles from the end of the supply edge): **${DYN_DSTEP_HZ} Hz** at
    ${DYN_DSTEP_ID}.
  - Worst residual frequency error on any settled plateau, AT THE
    BEST-RESOLVED HOLD PER CORNER (esc_rank in \`supply_dynamic.csv\`):
    **${DYN_MXFE}** at ${DYN_MXFE_ID} (criterion <= ${ACC_FERR}).
  - Minimum LOCK-flag level anywhere in the profile: **${DYN_MNLOCK} V** at
    ${DYN_MNLOCK_ID}.
  - Control-node travel from the high rail to the low rail:
    **${DYN_DVC} V** at ${DYN_DVC_ID}; peak excursion beyond the settled value
    during the step: **${DYN_VEX} V** at ${DYN_VEX_ID}.
  - **High-plateau settling escalation (#253): ${N_DYN_ESC} of ${N_DYN}
    corner(s)** missed \`ferr_hi\` at the default ${KD_TB_HI} hold and were
    re-run with the hold pushed to ${KD_TB_HI_X} -- **${V_DYN_SETTLE}**. See
    \`dyn_settling_rerun.csv\` and the Methodology section below for the
    per-corner classification.
  - **END-plateau settling escalation (#255): ${N_DEND} of ${N_DYN}
    corner(s)** missed \`ferr_end\` at their default post-ramp hold and were
    re-run with that hold extended by ${KD_DEND_TSTOP} past \`t_rend\` --
    **${V_DEND}**. See \`dyn_end_settling_rerun.csv\` and section 3c below.
  - **Overall criterion 3: ${V_DYN}** (${DYN_LOST} of ${N_DYN} runs failed the
    stays-locked criterion on some plateau, at the best-resolved hold)."
fi

# **Waveform retained** is a mandatory sim/README.md field and is therefore
# always emitted -- but it must describe what this run actually wrote.  The
# step/ramp transient is the only waveform this campaign keeps, and it exists
# only if a step/ramp run completed, so the claim is made against the files on
# disk rather than against the runner's intent.  Same for the Links entry: a
# record must not link evidence that was never produced.
WAVEFILES=("${CORNERSDIR}"/supply_transient_*.csv)
if [ "${#WAVEFILES[@]}" -eq 0 ]; then
  WAVE_FIELD="**N/A -- no step/ramp run completed, so no waveform was
    written.** The step/ramp transient is the only waveform this campaign
    retains; the steady-state grid's own transients are not kept (their
    measurements are, in \`supply_steady.csv\`), and no rawfile is written at
    any point. When criterion 3 is run, the transient is retained -- decimated
    to ${KD_DECIM} s per sample as
    \`corners/<record-id>/supply_transient_<corner>.csv\` (control node, LOCK
    flag, the rail itself and the feedback edge)."
  WAVE_LINK=""
else
  WAVE_FIELD="the step/ramp transient IS the argument for criterion 3, so it
    is kept -- decimated to ${KD_DECIM} s per sample as
    \`corners/${RID}/supply_transient_<corner>.csv\` (control node, LOCK flag,
    the rail itself and the feedback edge), never as a rawfile.
    ${#WAVEFILES[@]} file(s) written."
  WAVE_LINK="
  - Retained waveforms: \`corners/${RID}/supply_transient_*.csv\`"
fi

# The step/ramp profile's derived figures.  Every one of them is computed from
# the constants run.sh actually coded (and therefore from what was actually
# simulated); none is typed in.  This block exists because an earlier revision
# printed a hardcoded "40 us" ramp duration while passing the real endpoints
# into awk and discarding them, which left the record's Methodology disagreeing
# with the record's own Section 3 -- and with the deck -- by 6.25x.
KD_RATE="$(awk -v a="${KD_HI}" -v b="${KD_END}" -v t0="${KD_TRAMP%u}" -v t1="${KD_TREND%u}" \
  'BEGIN{printf "%.4g", (a-b)*1000/(t1-t0)}')"
# Ramp duration, us.
KD_DUR="$(awk -v t0="${KD_TRAMP%u}" -v t1="${KD_TREND%u}" 'BEGIN{printf "%.4g", t1-t0}')"
# The ramp and the step edge, each as a multiple of the loop's own KTAU.
KD_RAMP_TAU="$(awk -v d="${KD_DUR}" -v t="${KTAU%u}" 'BEGIN{printf "%.2f", d/t}')"
KD_STEP_TAU="$(awk -v e="${KD_TEDGE%n}" -v t="${KTAU%u}" 'BEGIN{printf "%.3g", t*1000/e}')"
# How much slower the ramp is than the step edge.
KD_RSRATIO="$(awk -v e="${KD_TEDGE%n}" -v d="${KD_DUR}" 'BEGIN{printf "%.3g", d*1000/e}')"
DYN_CORNERS="$(awk -F, '!/^#/ && $1 != "bundle" {printf "`%s`/%s C, ", $1, $2}' "${DYNCSV}" | sed 's/, $//')"
[ -n "${DYN_CORNERS}" ] || DYN_CORNERS="(none)"

# Per-(bundle,temp) frequency-deviation table, 15 rows.
FDEV_TABLE="$(awk -F, '
  !/^#/ && $1 != "bundle" {
    key = $1 "|" $2; band[key] = $4;
    if ($3 + 0 < 3.0)  { d297[key] = $6; v297[key] = $14; f297[key] = $5; s297[key] = flag($22) }
    if ($3 + 0 == 3.30){ f330[key] = $5; v330[key] = $14;                    s330[key] = flag($22) }
    if ($3 + 0 > 3.6)  { d363[key] = $6; v363[key] = $14; f363[key] = $5; s363[key] = flag($22) }
    order[key] = 1;
  }
  END {
    nb = split("typical ff ss fs sf", BU, " "); nt = split("-40 27 125", TE, " ");
    for (bi = 1; bi <= nb; bi++) for (ti = 1; ti <= nt; ti++) {
      k = BU[bi] "|" TE[ti];
      if (!(k in order)) continue;
      printf "  | %s | %s | %s | %s/%s/%s | %+.4g | %+.4g | %.3f / %.3f / %.3f | %.4g |\n",
        BU[bi], TE[ti], band[k], s297[k], s330[k], s363[k],
        d297[k], d363[k], v297[k], v330[k], v363[k],
        (v363[k] - v297[k]) / 0.66;
    }
  }
  function flag(v) {
    if (v == "PASS")       return "Y";
    if (v == "FAIL:ferr")  return "f";
    if (v == "FAIL:phi")   return "p";
    if (v == "FAIL:N")     return "N";
    if (v == "FAIL:fout")  return "o";
    if (v == "FAIL:lock")  return "L";
    if (v == "FAIL:power") return "P";
    return "?";
  }' "${STEADY}")"

# Per-(bundle,temp) static-phase table.
PHI_TABLE="$(awk -F, '
  !/^#/ && $1 != "bundle" {
    key = $1 "|" $2;
    if ($3 + 0 < 3.0)  { p297[key] = $8; s297[key] = $9 }
    if ($3 + 0 == 3.30){ p330[key] = $8; s330[key] = $9 }
    if ($3 + 0 > 3.6)  { p363[key] = $8; s363[key] = $9 }
    order[key] = 1;
  }
  END {
    nb = split("typical ff ss fs sf", BU, " "); nt = split("-40 27 125", TE, " ");
    for (bi = 1; bi <= nb; bi++) for (ti = 1; ti <= nt; ti++) {
      k = BU[bi] "|" TE[ti];
      if (!(k in order)) continue;
      printf "  | %s | %s | %.4g / %.4g / %.4g | %.4g / %.4g / %.4g | %+.4g |\n",
        BU[bi], TE[ti], p297[k]*1e9, p330[k]*1e9, p363[k]*1e9,
        s297[k]*1e9, s330[k]*1e9, s363[k]*1e9, (p363[k] - p297[k])*1e9;
    }
  }' "${STEADY}")"

# Per-corner power table, one row per (bundle,temp), three supplies per cell.
PWR_TABLE="$(awk -F, '
  !/^#/ && $1 != "bundle" {
    key = $1 "|" $2;
    v = $3 + 0;
    tag = (v < 3.0 ? "a" : (v > 3.6 ? "c" : "b"));
    P[key tag] = $21 * 1e3;
    C[key tag] = $3 * (($18 < 0) ? -$18 : $18) * 1e3;
    VV[key tag] = $3 * (($19 < 0) ? -$19 : $19) * 1e3;
    D[key tag] = $3 * (($20 < 0) ? -$20 : $20) * 1e3;
    S[key tag] = ($22 == "PASS" ? "Y" : "n");
    T[key tag] = $23;
    order[key] = 1;
  }
  END {
    nb = split("typical ff ss fs sf", BU, " "); nt = split("-40 27 125", TE, " ");
    for (bi = 1; bi <= nb; bi++) for (ti = 1; ti <= nt; ti++) {
      k = BU[bi] "|" TE[ti];
      if (!(k in order)) continue;
      printf "  | %s | %s | %s/%s/%s | %.3f / %.3f / %.3f | %.3f / %.3f / %.3f | %.3f / %.3f / %.3f | %.3f / %.3f / %.3f |\n",
        BU[bi], TE[ti], S[k "a"], S[k "b"], S[k "c"],
        C[k "a"], C[k "b"], C[k "c"], VV[k "a"], VV[k "b"], VV[k "c"],
        D[k "a"], D[k "b"], D[k "c"], P[k "a"], P[k "b"], P[k "c"];
    }
  }' "${STEADY}")"

# Step/ramp table.  The two trailing "hold" columns name the high-plateau and
# END-plateau windows THIS row was actually measured at ($50 t_hi_end_s, $52
# t_end_s) and flag an escalated row (esc_rank = $49, esc_rank_end = $51) with
# an asterisk, so a reader cannot mistake an escalated-and-still-failing
# corner for an unescalated one (#253, #255).
DYN_TABLE="$(awk -F, '
  !/^#/ && $1 != "bundle" {
    printf "  | %s / %s C | %.4g | %.4g | %.4g | %.4g | %.4g | %.3f / %.3f / %.3f | %.4g | %s%.4g us | %s%.4g us |\n",
      $1, $2, $5*1e9, maxa($7,$8,$9,$10)*1e9, maxa($13,$14,$13,$14)*1e9,
      $17, $19, $25, $26, $27, $39,
      ($49+0 == 1 ? "*" : ""), $50*1e6, ($51+0 == 1 ? "*" : ""), $52*1e6;
  }
  function maxa(a, b, c, d,   m) {
    m = ab(a); if (ab(b) > m) m = ab(b); if (ab(c) > m) m = ab(c); if (ab(d) > m) m = ab(d);
    return m;
  }
  function ab(x) { return x < 0 ? -x : x }' "${DYNCSV}")"

# High-plateau settling re-run table -- one row per corner that escalated.
# Consumed only inside the nested `$(if ... cat <<ESC ... ESC)` block in
# section 3b below, which is why shellcheck's usage tracking cannot see the
# reference (same shape as CMP_TABLE's own nested-heredoc use above).
# shellcheck disable=SC2034
DYN_SETTLE_TABLE="$(awk -F, '
  !/^#/ && $1 != "bundle" {
    printf "  | %s / %s C | %.4g us | %.4g | %.4g us | %.4g | %.4g | %s |\n",
      $1, $2, $4*1e6, $5, $6*1e6, $7, $8, $10;
  }' "${DYNSETTLE}")"

# END-plateau settling re-run table -- one row per corner that escalated.
# Consumed only inside the nested heredoc in section 3c below, so the linter's
# usage tracking cannot see the reference (same shape as DYN_SETTLE_TABLE
# immediately above).
# shellcheck disable=SC2034
DYN_END_TABLE="$(awk -F, '
  !/^#/ && $1 != "bundle" {
    printf "  | %s / %s C | %s | %.4g us | %.4g | %.4g us | %.4g | %.3g | %.3g | %s |\n",
      $1, $2, $3, $4*1e6, $5, $6*1e6, $7, $8, $9, $10;
  }' "${DYN_END_SETTLE}")"

# Power-split table at 3.30 V.
SPLIT_TABLE="$(awk -F, '
  !/^#/ && $1 != "bundle" && $3 + 0 == 3.30 {
    printf "  | %s C | %s | %.4g | %.4g | %.4g | %.0f %% |\n",
      $2, $4, $9*1e3, $10*1e3, ($9+$10)*1e3, 100*$10/($9+$10);
  }' "${POWER}" | sort -t'|' -k2,2n)"

if [ "${NOMQ_MW}" = "n/a" ]; then
  NOMTOT_MW="n/a"
else
  NOMTOT_MW="$(awk -v a="${NOMQ_MW}" -v b="${NOMD_MW}" 'BEGIN{printf "%.4g", a+b}')"
fi
[ -n "${SPLIT_TABLE}" ] || SPLIT_TABLE="  | -- | -- | -- | -- | -- | -- |"
if [ "${N_SPLIT}" -eq 0 ]; then
  SPLIT_NOM=""
else
  SPLIT_NOM="

  At the nominal corner (typical/27 C/3.30 V) the block draws
  **${NOMTOT_MW} mW**, of which **${NOMQ_MW} mW** is frequency-independent and
  **${NOMD_MW} mW** scales with frequency. Per domain, quiescent / dynamic:
  core ${NOMQC_MW} / ${NOMDC_MW} mW, VCO ${NOMQV_MW} / ${NOMDV_MW} mW,
  divider ${NOMQD_MW} / ${NOMDD_MW} mW. The worst corner of the reduced grid
  is ${SPLIT_MAX_ID} at ${SPLIT_MAX_MW} mW (${SPLIT_MAXQ_MW} quiescent,
  ${SPLIT_MAXD_MW} dynamic)."
fi
if [ "${N_SPLIT}" -eq 0 ]; then
  SPLIT_NOTE="**Not measured in this record.** The split needs a second locked
  operating point per corner and none completed inside this run's compute
  budget; the method is implemented (\`SIM_SPLIT_BUNDLES\` / \`SIM_SPLIT_TEMPS\`
  in the runner) and is stated in Methodology, but **no quiescent/dynamic
  number is reported here.** The per-domain totals above are the whole of this
  record's power result."
else
  SPLIT_NOTE=""
fi

# ---------------------------------------------------------------------------
# Supersession provenance.
# ---------------------------------------------------------------------------
# `sim/README.md`'s append-only rule says a re-run does not edit the record it
# replaces: it mints a new one carrying a **Supersedes** field.  That field is
# an ID, and an ID on its own leaves a reader holding two evidence records with
# no stated link between them beyond a filename -- which run of which campaign
# produced the baseline, at what commit, and what is different now.  So when
# this campaign supersedes an earlier record it also says so in prose, and
# every fact in that prose is READ OUT OF the superseded record and its own
# extracted-metrics CSV rather than restated by hand.  SIM_SUPERSEDES_PR names
# the pull request that landed the baseline (the one thing the record itself
# cannot know, because it is written before it is merged).
SUPERSEDE_PROSE=""
if [ -n "${SIM_SUPERSEDES:-}" ]; then
  PRIOR_MD="${RECORDSDIR}/${SIM_SUPERSEDES}.md"
  PRIOR_CSV="${EXP}/corners/${SIM_SUPERSEDES}/supply_steady.csv"
  # `|| true` on each: the superseded record is normally right there in
  # records/, but a runner pointed at a record id that is not on this checkout
  # must still mint an honest record saying so, not die inside `set -o pipefail`
  # on sed's exit status.
  PRIOR_COMMIT="$(sed -n 's/.*Repo commit: `\([^`]*\)`.*/\1/p' "${PRIOR_MD}" 2>/dev/null | head -1 || true)"
  # The record's own field is "<timestamp>, <author>"; only the timestamp is
  # wanted here, so the author is not restated as if it were part of a date.
  PRIOR_STAMP="$(sed -n 's/^- \*\*Timestamp \/ author\*\*: \([^,]*\).*$/\1/p' "${PRIOR_MD}" 2>/dev/null | head -1 || true)"
  PRIOR_N="$(awk -F, '!/^#/ && $1 != "bundle"' "${PRIOR_CSV}" 2>/dev/null | wc -l | tr -d ' ' || true)"
  PRIOR_TS="$(awk -F, '!/^#/ && $1 != "bundle" {print $23}' "${PRIOR_CSV}" 2>/dev/null | sort -u | tr '\n' ' ' | sed 's/ $//' || true)"
  : "${PRIOR_COMMIT:=(not stated in that record)}"
  : "${PRIOR_STAMP:=(not stated in that record)}"
  : "${PRIOR_N:=0}"
  : "${PRIOR_TS:=(not stated)}"
  # Read what the PRIOR record actually measured off ITS OWN extracted-metrics
  # CSVs (#253) -- never assumed. An earlier revision of this paragraph
  # hardcoded "that record reported [the settling re-run/power split/step-
  # ramp] as not measured", which was true of the FIRST supersession this
  # campaign ever did (the 9-corner record #62 -> the full-grid record #58)
  # but is false of any LATER one where the superseded record already
  # measured those things (e.g. #58 -> #253, which supersedes a record that
  # measured and FAILED criterion 3, not one that never measured it).
  PRIOR_RERUN_CSV="${EXP}/corners/${SIM_SUPERSEDES}/settling_rerun.csv"
  PRIOR_N_RERUN="$(awk -F, '!/^#/ && $1 != "bundle"' "${PRIOR_RERUN_CSV}" 2>/dev/null | wc -l | tr -d ' ' || true)"
  : "${PRIOR_N_RERUN:=0}"
  PRIOR_SPLIT_CSV="${EXP}/corners/${SIM_SUPERSEDES}/power_split.csv"
  PRIOR_N_SPLIT_ROWS="$(awk -F, '!/^#/ && $1 != "bundle"' "${PRIOR_SPLIT_CSV}" 2>/dev/null | wc -l | tr -d ' ' || true)"
  : "${PRIOR_N_SPLIT_ROWS:=0}"; PRIOR_N_SPLIT=$(( PRIOR_N_SPLIT_ROWS / 3 ))
  PRIOR_DYN_CSV="${EXP}/corners/${SIM_SUPERSEDES}/supply_dynamic.csv"
  PRIOR_N_DYN="$(awk -F, '!/^#/ && $1 != "bundle"' "${PRIOR_DYN_CSV}" 2>/dev/null | wc -l | tr -d ' ' || true)"
  : "${PRIOR_N_DYN:=0}"
  PRIOR_DYNSETTLE_CSV="${EXP}/corners/${SIM_SUPERSEDES}/dyn_settling_rerun.csv"
  PRIOR_N_DYN_ESC="$(awk -F, '!/^#/ && $1 != "bundle"' "${PRIOR_DYNSETTLE_CSV}" 2>/dev/null | wc -l | tr -d ' ' || true)"
  : "${PRIOR_N_DYN_ESC:=0}"
  SUPERSEDE_PROSE="
- **Supersession provenance** (which record this replaces, and how it got
  here): the baseline superseded below is
  \`sim/supply-sensitivity/records/${SIM_SUPERSEDES}.md\` -- $([ "${PRIOR_N}" -gt 0 ] && echo "${PRIOR_N}" || echo "an unrecorded number of") steady-state
  points of this same claim, every one of them run at ${PRIOR_TS}, minted
  ${PRIOR_STAMP} at repo commit \`${PRIOR_COMMIT}\`, landed on \`main\` by
  **${SIM_SUPERSEDES_PR:-(pull request not stated)}**. That record is **not**
  edited and is not withdrawn -- \`sim/README.md\` is append-only, so it stands
  as the evidence it was, and this record states the delta rather than
  overwriting it. The delta, read off that record's own extracted-metrics
  CSVs rather than assumed: ${N_STEADY} steady-state points here against
  ${PRIOR_N} there; ${N_RERUN} criterion-1 settling re-run(s) at ${KTSTOP_X}
  here against ${PRIOR_N_RERUN} there; ${N_SPLIT} corner(s) of the
  quiescent/dynamic power split here against ${PRIOR_N_SPLIT} there;
  ${N_DYN} supply step/ramp run(s) here against ${PRIOR_N_DYN} there; and,
  specifically for #253's own fix, ${N_DYN_ESC:-0} of those step/ramp
  corner(s) escalated to the longer ${KD_TB_HI_X} high-plateau hold here,
  against ${PRIOR_N_DYN_ESC} there (that record's step/ramp deck had no
  high-plateau escalation mechanism, so every one of its criterion-3 FAILs
  was measured once, at the shorter ${KD_TB_HI} hold, and reported as a bare
  FAIL rather than as resolved-or-genuine). Where a number appears in both
  records and differs, THIS record's is the one to cite for the corners it
  covers, and the reason is stated: a corner escalated to a longer hold (at
  either criterion) is a closer-to-settled measurement of the same operating
  point, not a different one."
fi

# ---------------------------------------------------------------------------
# Console summary
# ---------------------------------------------------------------------------
cat <<EOF
supply-sensitivity: ${N_STEADY} steady-state points, ${N_DYN} step/ramp runs
  frequency deviation vs nominal supply   worst ${WDEV_PPM} ppm @ ${WDEV_ID}      ${V_FREQ}
  static phase offset (REF->FB)           worst ${WPHI_NS} ns @ ${WPHI_ID}
  UP/DN pulse-width skew                  ${MNSK_NS} .. ${MXSK_NS} ns
  Vctrl (settled)                         ${MNVC} .. ${MXVC} V,  ${N_VOUT} point(s) outside ${ACC_VCTRL_LO}-${ACC_VCTRL_HI} V   ${V_VCTRL}
  total power @ 100 MHz                   ${MNP_MW} .. ${MXP_MW} mW (worst ${MXP_ID})    ${V_PWR}
  step/ramp: worst plateau ferr           ${DYN_MXFE} @ ${DYN_MXFE_ID}     ${V_DYN}
  settling re-runs @ ${KTSTOP_X}              ${N_RERUN}: ${N_R_SETTLES} settle, ${N_R_PHI} phi-only, ${N_R_INTEG} integration, ${N_R_UNDAMPED} under-damped, ${N_R_NOTLOCK} not locked
  step/ramp high-plateau re-runs @ ${KD_TB_HI_X}  ${N_DYN_ESC:-0}: ${N_DYN_RESOLVED:-0} resolved, ${N_DYN_GENUINE:-0} genuine, ${N_DYN_NOTLOCK:-0} not locked
  step/ramp END-plateau re-runs           ${N_DEND}: ${N_DEND_SETTLES} settle, ${N_DEND_UNDAMPED} under-damped
  lock-criterion failures                 ${N_FAIL} of ${N_STEADY}: ${FAILLIST}
EOF

# ---------------------------------------------------------------------------
# The record
# ---------------------------------------------------------------------------
cat >"${RECORDSDIR}/${RID}.md" <<EOF
# Record ${RID}

- **Record ID**: ${RID}
- **Claim**: #14 (design-input claim, and a pass/fail against one draft spec
  line) -- across the ratified 3.3 V +/- 10 % supply range and the full PVT
  grid, (a) how much does the CLOSED-LOOP output frequency deviate from its
  nominal-supply value, (b) how much does the static phase offset move with
  supply against the **post-#24** charge pump, (c) does the loop stay locked
  through a supply step and a supply ramp and how much disturbance couples
  through from the VCO supply pushing #8 measured open-loop, and (d) what is
  the quiescent and dynamic supply current with the loop locked at
  ${KFOUT} Hz, per block, against the draft < ${ACC_PWR_MW} mW target?
  The power target is the only pass/fail against a spec line and it is a
  placeholder pending ratification (#1): \`spec/pll.md#power\`. Everything else
  here is a design-input claim in the second form \`sim/README.md\` admits.${SUPERSEDE_PROSE}
- **Netlist provenance**: schematic (\`design/pll_top.sch\` (#52), exported by
  \`design/netlist.sh\` to \`design/netlist/pll_top.spice\`, assembled with the
  campaign stimulus by \`sim/lib/pll_top_dut.sh\`) ->
  - steady-state deck: \`sim/supply-sensitivity/netlist-snapshots/${RID}.spice\`,
    SHA-256 \`${SHA_LOCK}\`
  - step/ramp deck: \`sim/supply-sensitivity/netlist-snapshots/${RID}-dyn.spice\`,
    SHA-256 \`${SHA_DYN}\`

  **Charge-pump design revision, stated explicitly** (#14 acceptance criterion,
  absorbing #24): the \`cp\` inside \`pfd_cp\` in this DUT is the **post-#24,
  mitigated** charge pump -- \`design/cp_dumpbuf.sch\`, the Vctrl-tracking
  dump-node buffer that merged as PR #46. #24 documented that the
  pre-mitigation pump carried a **Vctrl-dependent** static phase offset
  (roughly +10 ns to -17 ns across the Vctrl window), and Vctrl at a fixed
  output frequency moves with supply, so on the pre-#24 design part of the
  static-phase-vs-supply number below would have come from the charge pump's
  dump node rather than from the loop. The numbers in this record are
  **not** comparable with #24's before-picture table.
- **Environment provenance**:
$(simenv_env_block "$(simenv_xschem_version) -- the DUT
    netlist is an xschem export of design/pll_top.sch, not a hand-written deck.")
- **Corner matrix run**:
  - **Steady state (criteria 1, 2, 4):** ${GRID_STATEMENT} --
    ${NB_RUN} process bundle(s) x ${NT_RUN} temperature(s) x ${NV_RUN} supplies
    = ${N_STEADY} points, listed exactly as run.
    - Bundles -> \`.lib\` sections of \`sm141064.ngspice\`:
      $(for b in ${GRID_BUNDLES_RUN}; do printf '`%s` -> %s; ' "${b}" "${b}"; done) each
      with \`${PASSIVES//,/, }\`.
    - Temperature: ${GRID_TEMPS_RUN// /, } C. Supply: ${GRID_VDDS_RUN// /, } V.$(
      if [ -n "${GRID_JUSTIFY}" ]; then cat <<'SUBSET'

    - **This is a SUBSET, and the reason is compute, which `sim/README.md`
      explicitly does not accept on its own ("the sim was slow" is not a
      justification).  So the reduction is stated as what it is -- an
      INCOMPLETE campaign -- rather than dressed up as a design argument.**
      One closed-loop point of this DUT at 100 MHz costs ~143 CPU-seconds per
      microsecond of transient on the machine this ran on, i.e. ~29 CPU-minutes
      per corner even after the warm-start work that removed the acquisition
      ramp; the full 45-point grid plus the step/ramp and power-split runs is
      ~20 CPU-hours, which was not available.  The axis kept at FULL resolution
      is the supply axis, because that is the axis this campaign exists to
      sweep and every one of its claims is a claim about it; the temperature
      axis is kept whole because quiescent current and VCO pushing both move
      with it.  The process axis is what was cut.
      **Consequence, stated plainly: the frequency, static-phase and power
      numbers below are NOT worst-case over process, and must not be cited as
      if they were.**  The follow-up issue filed alongside this record owns the
      remaining 36 points; the runner takes `SIM_BUNDLES` / `SIM_TEMPS` and
      re-running it over the full grid needs no code change.
SUBSET
      fi)
    - **Axes not swept: the passive process axes.** Every run pins
      \`res_typical\`, \`moscap_typical\`, \`mimcap_typical\` -- a MOS-only
      sweep, which \`sim/README.md\` requires a record to declare rather than
      leave implicit. Justification: the passive axes move the loop filter's
      R and C, i.e. the loop's BANDWIDTH and phase margin, and that is the
      claim \`sim/loop-dynamics\` (#10) owns and sweeps -- 27 passive bundles
      x 3 temperatures against the measured filter, over every legal
      (f_ref, N, Icp code) cell. The quantities THIS record reports are
      static in-lock quantities (settled frequency, settled phase offset,
      settled current) whose dependence on loop bandwidth is second-order:
      the loop's final state is set by the charge pump's charge balance and
      the VCO's f(Vctrl), not by how fast it got there. The one number here
      that IS bandwidth-dependent -- the step/ramp disturbance of criterion 3
      -- is reported with that dependence named, and \`sim/loop-dynamics\`
      is the record that bounds it over the passive corners.
    - Configuration per corner: N = ${KN} (of the ratified 4-64),
      f_ref = ${KFREF} Hz (of the ratified 1-25 MHz), Icp trim code
      ${KTRIM} of 4, VCO band code **chosen per (bundle, temperature)** --
      see Methodology; it is a static input and cannot be re-chosen when the
      supply moves.
  - **Settling re-run (criterion 1c): ${N_RERUN} corner(s)** of the ${N_STEADY}
    above re-simulated at ${KTSTOP_X} instead of ${KTSTOP_BASE}, selected by
    the runner from the measured residual frequency error rather than by hand;
    of those, **${N_R_INTEG} plus ${N_MARGIN} corner(s) were then re-simulated a
    third time** at the same ${KTSTOP_X} with the internal timestep ceiling
    tightened from ${KTMAX_BASE} to ${KTMAX_X}. Not separate corner axes -- the
    same corners, run longer and then run finer, so that a lock-criterion miss
    can be attributed to the transient budget, to the integration, or to the
    design, which are three different claims. See Result section 1c.
  - **Quiescent/dynamic power split (criterion 4): ${N_SPLIT} corner(s)**$(
      if [ "${N_SPLIT}" -eq 0 ]; then printf ' -- **none run.**  No
    quiescent/dynamic number appears in this record; see the Result section.'
      else printf ', each
    run a SECOND time locked at %s Hz.  Justified in Methodology: the split
    re-attributes a current the grid already reports, between two columns.' "${KFOUT2}"; fi)
  - **Supply step/ramp (criterion 3): ${N_DYN} corner(s)** -- ${DYN_CORNERS}.
    The supply axis is not a grid axis for these runs because the
    supply is the swept variable INSIDE each run: one transient carries a
    ${KD_LO} -> ${KD_HI} V step and a ${KD_HI} -> ${KD_END} V ramp, so each
    run visits all three supply points of the grid. Justified in Methodology.
  - **Per DR-002 Decision 3: no separate supply-FLAVOUR sweep applies.** v1 is
    3.3 V thick-oxide only; there is no 1.8 V or 5 V device flavour in this
    block, so the 2.97 / 3.30 / 3.63 V axis above is the complete supply-axis
    requirement for v1 and this campaign discharges it in full.
- **Methodology / criteria / limitations**:
  - **DUT assembly**: \`design/netlist/pll_top.spice\` (the committed export of
    \`design/pll_top.sch\`) prepended to the campaign's stimulus fragment by
    \`sim/lib/pll_top_dut.sh\`, the single path from \`design/pll_top.sch\` to
    a runnable deck. Nothing here is a hand-transcribed copy of the design,
    and the frozen snapshots above are self-contained. **Naming note:** that
    helper is #52's \`sim/lib/assemble_closed_loop.sh\`, renamed because
    \`main\` already has a differently-shaped helper at that path (#12 /
    PR #56, which concatenates block exports rather than instantiating
    \`pll_top\`). The two coexist until they are reconciled; the frozen
    snapshots and the testbench comments inside them name the pre-rename path,
    and it is the same file.
  - **Operating point, and where it comes from.** The VCO band code and the
    warm-start control voltage are DERIVED, per corner, from #8's committed
    f(Vctrl) evidence (\`${VCO_TUNING#"${ROOT}/"}\`) by
    linear interpolation inside the one bracketing interval of the measured
    curve -- never extrapolated. For each (bundle, temperature) the band is
    the single code that reaches ${KFOUT} Hz at **all three** supplies with
    the control voltage closest to mid-window. Choosing it per (bundle,
    temperature) rather than per corner is load-bearing: band select is a
    static input with no calibration FSM (DR-001 Decision 2), so re-choosing
    it when the supply moves would measure a different configuration at each
    supply and call the difference "supply sensitivity".
  - **The warm start is calibrated against THIS DUT, not assumed from #8.**
    #8's f(Vctrl) table is measured on the STANDALONE VCO, whose \`CLK\` drives
    only its own output buffer; inside \`pll_top\` the same \`CLK\` also drives
    the divider chain's input inverters, and that extra load shifts f(Vctrl)
    enough to matter -- at typical/27 C/3.30 V the #8-derived prediction is
    2.17 V where the loop actually settles above 2.4 V, a ~14 % frequency
    error. Left uncorrected that is ~5 loop time constants (46 us) of pure
    settling at every corner. So each corner is first measured OPEN LOOP on
    this same deck with \`VCTRL\` pinned by an ideal source (\`rforce\` = 1 mohm)
    at two control voltages ${KVPRE_D} V apart straddling #8's prediction, and
    the two measured (Vctrl, f_out) points are solved for the control voltage
    that gives the target frequency. The closed-loop run then starts there
    (\`rforce\` = ${KVPRE_ROFF} ohm, i.e. 3 fA -- not present). This is a
    correction derived from a measurement of the DUT, not a fitted fudge
    factor, and the two forced points are committed with the rest of the raw
    logs. #8's table still chooses the BAND; only the fine control voltage is
    re-derived.
  - **Warm start, not cold start.** \`.ic v(vctrl)\` **and**
    \`.ic v(xdut.xlf.nz)\` = the calibrated lock point for that corner. Setting
    \`VCTRL\` alone is not a warm start and this campaign learned it the
    expensive way: \`loop_filter\` is R in series with C1 (122 pF of MOS cap,
    node \`NZ\`) with C2 across \`VCTRL\`, and the loop's state lives on C1. A
    run that pre-charges \`VCTRL\` and leaves \`NZ\` at 0 V bleeds that charge
    through R and then has to ramp 122 pF to the lock point at the pump's few
    microamps -- tens of microseconds of pure acquisition inside what was
    supposed to be a settled measurement. Both nodes are therefore initialised
    to the same voltage, which is also their true relationship in lock (zero
    average current through R). The loop pulls the remainder. Cold-start
    acquisition is \`sim/pll-top-smoke\` (#52)'s claim and \`sim/lock-time\`
    (#12)'s campaign, and repeating it ${N_STEADY} times here would add the
    acquisition ramp to every run for no number this record reports. The
    residual is **not** assumed away: at ${KTA} and ${KTB} the default-length
    run is only ${KTA_TAU} and ${KTB_TAU} loop time constants in, so the lock
    criterion below is applied to the measured late-window numbers exactly as
    it would be after a cold start, and a corner whose calibration was poor
    fails the residual-frequency check rather than quietly reporting a
    half-settled number. Read the \`ferr\` column as a settling residual, not
    only as a steady-state error.
  - **A failed residual-frequency check is escalated, not recorded.** Because
    that column IS a settling residual, a corner that fails it at
    ${KTSTOP_BASE} has not been shown to be a design failure -- it has been
    shown to be unsettled, which is a different claim. The runner therefore
    re-runs every such corner at ${KTSTOP_X} (${KTSTOP_X_TAU} tau, late window
    ${KTA_X}/${KTB_X} = ${KTA_X_TAU}/${KTB_X_TAU} tau); and any corner still
    over threshold there is re-run once more at the same length with the
    timestep ceiling put back on the shared bound ${KTMAX_X}, because a third
    explanation -- the integration stepping over the PFD's internal set pulse,
    which PR #64 measured on this DUT -- has to be excluded before a residual
    can be called a property of the loop.  On a grid run AT the bound that
    exclusion is already made and the stage does nothing; it exists for the
    bound-sensitivity run that deliberately is not. The record reports all the runs a corner got and
    classifies it from the best-resolved one (section 1c). Both escalations are
    automatic -- \`SIM_EXTEND\`, \`SIM_EXTEND_TSTOP\`/\`_TA\`/\`_TB\`,
    \`SIM_EXTEND_MAX\`, \`SIM_FINE\`, \`SIM_FINE_TMAX\`, \`SIM_FINE_MAX\` in the
    runner -- rather than a note asking a later reader to follow them up,
    because the version of this campaign that left it as a note produced a
    record whose headline verdict could not be interpreted.
  - **Lock criterion** (same form as \`sim/pll-top-smoke\`, so the verdicts are
    comparable): residual fractional frequency error <= ${ACC_FERR}, measured
    as the DRIFT of the REF->FB phase between t = ${KTA} and t = ${KTB} (in a
    type-II loop a residual frequency error slips the phase linearly at
    exactly df/f seconds per second); static phase error <= ${ACC_PHI_FRAC} of
    a reference period; f_out/f_fb = N +/- ${ACC_NTOL}; |f_out - N f_ref| /
    N f_ref <= ${ACC_FERR}; LOCK-flag late-window average >= ${ACC_LOCK_FRAC}
    of the rail. Both phase instants sit on a reference HALF-period, so the
    REF and FB rises a probe pairs are the same cycle's and the measurement
    cannot alias by a whole reference period.
  - **Static phase offset, measured two independent ways.** (a) the REF -> FB
    edge skew the loop stands off, and (b) the UP/DN pulse-WIDTH difference at
    the PFD that produces it, sampled at three instants two reference periods
    apart so a single anomalous cycle shows up as a spread rather than as the
    value. In a reset-type PFD both outputs pulse every cycle for the reset
    delay and the loop stands off exactly the phase whose extra UP charge
    cancels the pump's per-event charge asymmetry, so w_up - w_dn and the
    REF->FB skew are the same quantity read at different nodes. They are
    reported side by side precisely so a disagreement is visible as the
    measurement error it would be.
  - **Frequency deviation vs. supply is reported against the same corner's
    nominal-supply value**, not against N*f_ref: \`fdev_ppm\` = (f_out(vdd) -
    f_out(3.30 V)) / f_out(3.30 V) for the same (bundle, temperature). See the
    Result section for why this number is small BY CONSTRUCTION in a locked
    loop and what the substantive supply-sensitivity observable is instead.
  - **Quiescent vs. dynamic current.** There is no "stop the clock" state in
    which to measure a quiescent current here: the ring VCO's starving current
    IS its oscillation current, and a PLL with a stopped reference is not a
    locked PLL. So the split is measured as what it means -- the
    frequency-INDEPENDENT and frequency-PROPORTIONAL parts of the same current
    -- by locking the same loop at a second output frequency (${KFOUT2} Hz,
    same N, half the reference, so every switching node scales together) and
    fitting I(f) = I_q + k*f per domain through the two points. Two points fit
    a two-parameter model exactly, so the fit has no residual to report and
    its accuracy is the accuracy of its two endpoints; a third frequency would
    turn it into a regression and is a reasonable extension, not a correction.
  - **Per-block attribution is per supply DOMAIN, and that is a real limit.**
    \`pll_top\` brings out three supply pins and they are the finest
    granularity at which current is separable without editing the design:
    \`VDD\` -> \`pfd_cp\` (PFD **and** charge pump) + \`lock_detector\`;
    \`VDD_VCO\`/\`GND_VCO\` -> the VCO (bias, band mirrors, V->I converter,
    ring, output buffer); \`VDD_DIV\` -> \`divider_chain\` (div-2/3 cells, the
    VCO-rate retiming flop, and the CLK-rate input inverters that drive them).
    \`loop_filter\` is passive and draws no supply current. So of #14's named
    blocks, **VCO and divider are separated; charge pump and PFD are not**,
    and there is no separate output-buffer block in this architecture -- the
    VCO's own output buffer is inside the VCO domain and the divider's input
    inverters are inside the divider domain. Splitting the charge pump from
    the PFD would need a fourth supply pin on \`design/pll_top.sch\`, which is
    #52's file and a design change, not a measurement change. Recorded as a
    gap rather than papered over with an estimate: **no number in this record
    attributes current to the charge pump alone.**
  - **Supply step and ramp: the rates, stated.** One transient per corner
    carries both events, separated by enough settling that neither
    contaminates the other. Both rates are quoted against the loop's own
    settling time constant \`KTAU\` = ${KTAU} (1/(2 pi R C1) = 17.1 kHz), which
    is the only timescale the loop has. The **step** is ${KD_LO} -> ${KD_HI} V
    with a ${KD_TEDGE} edge at t = ${KD_TSTEP} -- KTAU/${KD_STEP_TAU}, i.e. a
    step as far as the loop is concerned. The **ramp** is ${KD_HI} ->
    ${KD_END} V over ${KD_DUR} us (t = ${KD_TRAMP} to ${KD_TREND}), i.e.
    ${KD_RATE} mV/us. That is **${KD_RAMP_TAU} KTAU**: ${KD_RSRATIO}x slower
    than the step edge, but still FASTER than the loop's own settling, so the
    ramp is **not** a quasi-static tracking test -- it moves the rail on the
    same timescale the loop responds on, which is where a loop with no margin
    visibly lags. The two events therefore probe rejection at two rates a
    factor of ${KD_RSRATIO} apart, one far above the loop's response and one
    just above it. **A true tracking test needs a ramp of several KTAU and is
    not part of this profile**; adding one is follow-up work, not a
    reinterpretation of these rates. Twelve REF->FB phase probes are placed
    across the profile, each snapped onto a reference half-period.
  - **VCO supply pushing is CITED, not re-derived.** #8 measured it open loop:
    **${CITE_PUSH_WORST} %/V** worst-case static (median
    ${CITE_PUSH_MEDIAN} %/V) and **${CITE_STEP_WORST} MHz/V** transient for a
    0.1 V step at the 100 MHz-class operating point --
    \`sim/vco-tuning-range/records/${CITE_VCO_RECORD}.md\`, sections 1 and 2.
    This record measures what the CLOSED loop does with that pushing, which is
    a different quantity: inside the loop bandwidth the PLL corrects the VCO's
    excursion and outside it does not. The consistency check between the two
    is in the Result section.
  - **Simulator settings**: \`.tran ${KTSTEP} ${KTSTOP_BASE} 0 ${KTMAX_BASE}\`
    for the steady-state runs (\`.tran ${KTSTEP} ${KTSTOP_X} 0 ${KTMAX_BASE}\`
    for the ${N_RERUN} escalated corner(s), and
    \`.tran ${KTSTEP} ${KTSTOP_X} 0 ${KTMAX_X}\` for the ${N_R_INTEG} plus
    ${N_MARGIN} corner(s) the timestep-ceiling cross-check reached -- the
    \`tstop\` and \`tmax\` columns of \`supply_steady.csv\` say which is which,
    per row) and \`.tran ${KTSTEP} ${KD_TSTOP} 0 ${KTMAX_BASE}\` for the
    step/ramp runs; \`reltol 1e-3\`, \`abstol 1e-13\`, \`vntol 1e-6\`,
    \`rshunt 1e12\`, \`itl4 200\`.
  - **The timestep ceiling is the repo's shared closed-loop bound, not this
    campaign's own number.** ${KTMAX_BASE} is \`SIMENV_CLOSED_LOOP_TMAX\`
    (\`sim/lib/simenv.sh\`, documented in \`sim/README.md\`), and the runner
    refuses to start if its own copy of the literal has drifted from it. The
    bound is set by \`design/edgedet.sch\`'s INTERNAL set pulse (0.33-0.39 ns),
    **not** by the 1.1-1.9 ns UP/DN OUTPUT pulse and not by f_out: an integrator
    whose step is comparable to the set pulse steps clean over it on a large
    fraction of feedback edges, and the loop then reads as jammed with UP
    asserted while the feedback is already faster than the reference -- a false
    "does not lock", not a noisy one. #52 / PR #64 measured that failure mode on
    this DUT; #65 / PR #75 hoisted the bound so every closed-loop campaign
    inherits one value.

    **This campaign previously ran at 400 ps**, derived from the UP/DN output
    pulse -- the wrong pulse. The 9-corner record this one supersedes
    (\`20260801-024935-c4fe724\`) was taken at that ceiling and is qualified by
    the bound; it is not edited and not retracted, and re-examining it directly
    is #69's scope, not this record's. What this record can say is that its own
    numbers were taken at the bound.

    A run deliberately taken off the bound (\`SIM_TMAX\`, the bound-sensitivity
    study \`sim/lib/simenv.sh\` sanctions) is not silently mixed in: it gets its
    own work directory, its ceiling appears in the \`tmax\` column of every row
    it produced, and section 1c re-runs any corner it left failing at the bound
    before this campaign is allowed to call that corner a design-margin finding
    -- because "under-damped" and "under-resolved" are different claims. A
    corroborating in-band check that the integration is resolving the PFD at
    every corner reported here, measured rather than argued: the UP/DN widths in
    section 2 are 1-3 ns with BOTH branches pulsing every reference cycle, and a
    stepped-over set pulse leaves the corresponding branch dead.
  - **Waveform retained**: ${WAVE_FIELD}
  - **Limitations**:
    - **Schematic-level, no parasitics.** Every block's own record carries the
      same caveat; #18 owns the extracted re-run, and it is the record that
      supersedes these numbers, not a correction to them.
    - **Ideal bias.** \`IBN\`/\`ICN\`/\`IBP\`/\`ICP\` are driven from ideal
      current sources at 4x the unit-leg current, as every charge-pump
      campaign in this repo does, and they are held CONSTANT through the
      supply excursion. The bias generator is a separate, unbuilt block
      (design/README.md); assigning it a supply dependence here would be
      inventing one. **The supply sensitivity reported below therefore
      excludes whatever the real bias generator contributes**, and that is a
      first-order omission for a block whose charge-pump current sets the loop
      gain. It is the single largest caveat on this record.
    - **Ideal reference.** A pulse source with 200 ps edges and no jitter. In
      the steady-state deck its amplitude tracks the supply (a CMOS input on
      the same rail); in the step/ramp deck it is deliberately held at the
      nominal rail so the measured disturbance is the loop's response to the
      SUPPLY and not to a simultaneous change in its own input amplitude.
    - **One reference frequency, one N, one Icp code.** ${KFREF} Hz, N = ${KN},
      code ${KTRIM}. Supply sensitivity of the loop's static state is set by
      the VCO's f(Vctrl, vdd) and the pump's charge balance, neither of which
      is strongly N-dependent, but this record does not demonstrate that and
      does not claim it. \`sim/loop-dynamics\` (#10) covers the (f_ref, N,
      code) cross-product for the bandwidth question.
    - **No spur or jitter claim.** Control-line ripple appears here only as
      the Vctrl min/max spread. Reference spurs and jitter are #13
      (\`period-jitter\`); the ripple-vs-C2 trade is #10's section 7.
  - Statistical switches: \`sw_stat_global = sw_stat_mismatch = 0\` (nominal
    per-corner skew, no Monte Carlo mismatch).
- **Statistical convention**: N/A -- this is a corner-matrix claim, not a
  distribution claim. Charge-pump device mismatch, which adds a random
  component to the static phase offset measured below, is #15's
  \`mc-cp-mismatch\` campaign and is additive to these numbers.
- **Result**:

  ### 1. Supply sensitivity -- output frequency (criterion 1)

  **What this number is, and why it is small.** With the loop LOCKED, the
  output frequency is pinned to N x f_ref by the feedback -- that is what a PLL
  is for -- so \`fdev_ppm\` measures the loop's residual error, not the VCO's
  supply sensitivity. Reporting only this column would report a
  supply-sensitivity result of "approximately zero" and would be worthless.
  The substantive observable is the **control voltage the loop has to move to
  hold that frequency**: dVctrl/dVdd is the VCO supply pushing the loop
  absorbed, and the headroom left in the control window is what actually runs
  out at the supply extremes. Both are in the table.

  | Bundle | Temp | Band | lock check @2.97/3.30/3.63 | fdev @2.97 V (ppm) | fdev @3.63 V (ppm) | Vctrl @2.97/3.30/3.63 (V) | dVctrl/dVdd (V/V) |
  |---|---|---|---|---|---|---|---|
${FDEV_TABLE}

  Lock-check key: \`Y\` = every check passed; \`f\` = residual frequency
  error over threshold (still converging); \`p\` = static phase error over
  threshold; \`N\` = divide ratio wrong; \`o\` = absolute output frequency
  off target; \`L\` = the block's own LOCK flag did not assert; \`P\` = over
  the power budget. \`L\` alone -- everything electrical settled but the
  window comparator did not assert -- is a statement about the lock detector's
  window, not about the loop; the per-corner \`verdict\` column of
  \`corners/${RID}/supply_steady.csv\` names the failing check for every row.

  Transient length per corner is in the \`tstop\` column of that same CSV, and
  it is **not** one number for the whole grid. A corner whose residual
  frequency error was still over threshold at the default ${KTSTOP_BASE} was
  re-run automatically at ${KTSTOP_X} and it is the LONGER run that appears in
  the table above -- because that is the measurement closer to settled. The
  shorter run is kept as the other half of the comparison in
  \`corners/${RID}/settling_rerun.csv\`, and section 1c resolves each escalated
  corner as either a transient-budget artefact or a genuine design-margin
  finding. ${N_RERUN} corner(s) were escalated.

  - Worst frequency deviation from the nominal-supply value anywhere on the
    grid: **${WDEV_PPM} ppm** at ${WDEV_ID} (criterion: <= ${ACC_FDEV_PPM} ppm).
  - Worst residual fractional frequency error: **${WFERR}** at ${WFERR_ID}
    (criterion: <= ${ACC_FERR}).
  - Control-voltage slope dVctrl/dVdd across the +/-10 % rail:
    **${MNSLOPE} .. ${MXSLOPE} V/V** (mean ${AVSLOPE}), most sensitive at
    ${MXSLOPE_ID}, least at ${MNSLOPE_ID}.
  - Settled control voltage over the whole grid: **${MNVC} .. ${MXVC} V**
    (lowest ${MNVC_ID}, highest ${MXVC_ID}) -- these are the AVERAGE control
    voltages, \`vctrl_avg_v\`. Points outside DR-001 Decision
    2's usable ${ACC_VCTRL_LO}-${ACC_VCTRL_HI} V window: **${N_VOUT}** --
    ${VOUT}. **${V_VCTRL}** The window check deliberately uses a different
    statistic from the range above it: it tests \`vctrl_min_v\`/\`vctrl_max_v\`,
    i.e. the RIPPLE PEAKS, not the average, because headroom is lost at the
    peak of the ripple and a corner whose average sits inside the window while
    its peak leaves it has left it. So the count can exceed what the averages
    alone would suggest; that is the check working, not an inconsistency.
  - **Overall criterion 1: ${V_FREQ}** -- ${N_SETTLED} of ${N_STEADY} corners
    met the full lock criterion.

  **WHICH CHECK FAILED, AND WHO OWNS IT.** "${N_FAIL} of ${N_STEADY} corners
  failed" is not an actionable statement, because the lock criterion is five
  checks against three different blocks and they route to three different
  places. The breakdown, from the \`verdict\` column of \`supply_steady.csv\`:

  - **residual frequency error over ${ACC_FERR}: ${N_F_FERR} corner(s).** These
    are the settling question, and section 1c resolves each of them as a
    transient-budget artefact, an integration artefact, or a genuine
    design-margin finding. This is the only class that can reach #10 / #8.
  - **static phase error over ${ACC_PHI_FRAC} of a reference period:
    ${N_F_PHI} corner(s)** -- ${PHI_LIST}. Settled in frequency, but standing
    off more phase than the criterion allows. That is the charge pump's
    per-event charge asymmetry (\`pfd_cp\`, #9, post-#24), read against the
    same criterion \`sim/pll-top-smoke\` applies; section 2 reports the number
    itself and #15's \`mc-cp-mismatch\` adds the random component on top.
  - **block's own LOCK flag below ${ACC_LOCK_FRAC} of the rail:
    ${N_F_LOCK} corner(s)** -- ${LOCK_LIST}. At these corners everything
    electrical settled and the window comparator did not assert, which is a
    statement about **\`lock_detector\` (#11)'s window**, not about the loop.
    It is flagged there rather than counted as a loop failure, and this record
    does not propose a window change -- that is #11's call with its own
    evidence.
  - **divide ratio or absolute output frequency wrong: ${N_F_RANGE}
    corner(s)** -- ${RANGE_LIST}. Not a damping finding: the loop is not in
    lock at that corner at all, which is a lock-RANGE question about whether
    the chosen band reaches ${KFOUT} Hz there, i.e. #8's f(Vctrl) table and
    the band choice derived from it.

  **THE SETTLING BUDGET, AND WHICH ROWS ARE ENTITLED TO BE READ AS
  STEADY-STATE.** The lock-check column is the lock criterion applied at the
  corner: \`Y\` means the residual frequency error, the static phase error,
  the divide ratio, the absolute output frequency and the block's own LOCK
  flag all met their stated thresholds in the late window; any other letter
  names the check that did not. **${N_UNSETTLED} of ${N_STEADY} corners are
  not \`Y\`, and at
  those corners the f_out, phase and power numbers in this record are samples
  of a loop that is still converging -- not settled values, and not to be
  quoted as such.** The default run is ${KTSTOP_BASE} long against a loop time
  constant of ${KTAU} (${KTB} is ${KTB_TAU} tau), so a corner whose
  phase-acquisition transient was large has not finished at that length.

  **That is the point at which this record stops guessing and runs the corner
  again.** Every such corner was re-simulated at ${KTSTOP_X}
  (${KTSTOP_X_TAU} tau), and section 1c below states, per corner, whether it
  settles and passes once given the time -- in which case the short run's
  verdict was an artefact of the transient budget -- or whether it is still
  outside the criterion at four time constants, in which case it is a
  design-margin finding and is flagged as one. The two are different claims
  and this record does not let them share a row.

  **Consistency with #8's open-loop pushing.** The loop holds f_out fixed by
  moving Vctrl against the VCO's supply pushing, so the measured dVctrl/dVdd
  and #8's measured pushing are two views of one mechanism:
  dVctrl/dVdd ~ -(df/dVdd) / Kvco. With #8's median static pushing of
  ${CITE_PUSH_MEDIAN} %/V at 100 MHz (i.e. about -39 MHz/V) and its measured
  Kvco of 38-135 MHz/V in the bands this operating point uses, that predicts a
  slope of roughly 0.3-1.0 V/V. The measured ${MNSLOPE} .. ${MXSLOPE} V/V sits
  inside that envelope, which is the cross-check: the closed loop is absorbing
  the pushing #8 characterised, through the control node, exactly as expected.

  ### 1c. The re-runs: budget artefact, integration artefact, or genuine margin?

${SETTLE_PROSE}

${MARGIN_NOTE}

  ### 2. Supply sensitivity -- static phase offset (criterion 2)

  Measured against the **post-#24** charge pump (\`design/cp_dumpbuf.sch\`,
  PR #46) -- see Netlist provenance. Two independent measurements of the same
  quantity: the REF->FB edge skew the loop stands off, and the UP/DN
  pulse-WIDTH difference at the PFD that produces it.

  | Bundle | Temp | REF->FB phase @2.97/3.30/3.63 (ns) | UP-DN width skew @2.97/3.30/3.63 (ns) | d(phase) over the rail (ns) |
  |---|---|---|---|---|
${PHI_TABLE}

  - Worst static phase offset anywhere on the grid: **${WPHI_NS} ns** at
    ${WPHI_ID}; the criterion is ${ACC_PHI_FRAC} of a reference period
    ($(awk -v f="${KFREF}" -v p="${ACC_PHI_FRAC}" 'BEGIN{printf "%.4g", p/f*1e9}') ns at ${KFREF} Hz).
  - UP/DN pulse-width skew over the grid: **${MNSK_NS} .. ${MXSK_NS} ns**
    (most negative ${MNSK_ID}, most positive ${MXSK_ID}).
  - Worst cycle-to-cycle spread of the skew across its three probes:
    **${WSPREAD_NS} ns**, at ${WSPREAD_ID} -- the measurement's own
    repeatability, and the scale below which a difference between two cells of
    the table is not a result.

  ### 3. Supply step and ramp while locked (criterion 3)

  Profile per run: hold at ${KD_LO} V; **step** to ${KD_HI} V with a
  ${KD_TEDGE} edge at t = ${KD_TSTEP}; settle; **ramp** down to ${KD_END} V
  between t = ${KD_TRAMP} and t = ${KD_TREND} -- ${KD_DUR} us, ${KD_RATE}
  mV/us, ${KD_RAMP_TAU} KTAU; settle.

  | Corner | phase, pre-step (ns) | peak phase excursion, step (ns) | peak phase excursion, ramp (ns) | residual f error, low plateau | ... end plateau | Vctrl low/high/end (V) | LOCK min (V) | hold, high | hold, end |
  |---|---|---|---|---|---|---|---|---|---|
${DYN_TABLE:-  | -- | -- | -- | -- | -- | -- | -- | -- | -- | -- |}

  \`hold, high\` and \`hold, end\` are the two plateau windows' end instants
  this row was actually measured at; \`*\` marks that plateau escalated past
  its default (${KD_TB_HI} high, ${KD_TSTOP_BASE} end) -- see 3b and 3c below.

${DYN_BULLETS}

  The step is where #8's open-loop transient pushing (${CITE_STEP_WORST} MHz/V
  for a 0.1 V step, i.e. about -0.16 % per 0.1 V at 100 MHz) enters: it walks
  the VCO instantaneously, and the loop then pulls it back with a time
  constant set by its own bandwidth. The phase excursion above is the integral
  of that error while the loop corrects it, which is the number a system-level
  jitter budget consumes -- **not** #8's open-loop figure, and not a
  re-derivation of it.

  ### 3b. High-plateau settling escalation (criterion 3)

  The same question criterion 1's own settling re-run answers for the
  steady-state grid, asked of the step/ramp deck's high plateau (#253): a
  corner whose \`ferr_hi\` misses ${ACC_FERR} at the default
  ${KD_TB_HI} window (only ${KD_TA_HI}..${KD_TB_HI} after the step edge ends
  -- LESS settling time than criterion 1's own default late window) has not
  been shown to fail the stays-locked criterion, only to still be settling.
  Every corner that misses it is re-run automatically with the high-plateau
  hold pushed to ${KD_TB_HI_X} (the ramp, and everything after it, pushed out
  by the same amount so its own rate and duration do not change) before being
  called a design result.

$(if [ "${N_DYN_ESC:-0}" -eq 0 ]; then
cat <<NOESC

  N/A -- every step/ramp corner in this record met the stays-locked criterion
  at the default ${KD_TB_HI} hold, so nothing escalated.
NOESC
else
cat <<ESC

  | Corner | hold, short | ferr_hi, short | hold, long | ferr_hi, long | LOCK, long (V) | classification |
  |---|---|---|---|---|---|---|
${DYN_SETTLE_TABLE}

  \`classification\`: \`resolved\` = ferr_hi came inside ${ACC_FERR} at the
  longer hold -- a settling-budget artefact, the same fate every one of
  criterion 1's apparent failures had on this grid (section 1c); \`genuine\` =
  still outside ${ACC_FERR} with the loop otherwise in lock -- a design-margin
  finding, evidence that a large supply step, not just steady-state phase
  margin, is where this operating point's loop-bandwidth margin binds, routed
  to \`sim/loop-dynamics\` (#10); \`not-locked\` = the LOCK flag itself never
  recovers on the escalated hold, a lock-range finding rather than a damping
  one.

  **Result: ${V_DYN_SETTLE}.** ${N_DYN_GENUINE:-0} genuine, ${N_DYN_NOTLOCK:-0}
  not-locked corner(s) at the escalated hold: ${DYN_MARGIN_LIST:-(none)}.
ESC
fi)

  ### 3c. END-plateau settling escalation (criterion 3)

  3b asks the settling-budget question of the HIGH plateau, the hold after the
  STEP; this asks the identical question of the END plateau, the hold after
  the RAMP, measured over \`p11\`..\`p12\` and reported above as \`ferr_end\`
  (#255).  A corner whose \`ferr_end\` misses ${ACC_FERR} inside the default
  ${KD_TSTOP_BASE} post-ramp hold has not been shown to fail the stays-locked
  criterion -- only to still be converging after the ramp -- so the runner
  re-runs it with \`p11\`/\`p12\`/\`tstop\` pushed to \`t_rend\` +
  ${KD_DEND_TA}/${KD_DEND_TB}/${KD_DEND_TSTOP} before this record calls it
  either way.  Those are the SAME \`KTA_X\`/\`KTB_X\`/\`KTSTOP_X\` offsets
  criterion 1's escalation uses, measured from \`t_rend\` (where post-ramp
  convergence starts) rather than from t = 0, so an escalated END plateau gets
  exactly the settling budget criterion 1 already grants a still-converging
  corner -- not a shorter one, and not a second budget invented here.

  They are OFFSETS rather than absolute instants so that this escalation
  COMPOSES with 3b's: a corner that missed both plateaus is re-run once, on
  the high-plateau-escalated profile, with the post-ramp hold extended from
  **that** profile's own \`t_rend\` -- so exactly one row per corner is the
  best-resolved one on both plateaus at once, and \`supply_dynamic.csv\`'s
  "longest hold wins" rule stays a total order rather than a coin toss between
  two half-resolved rows.  On the unescalated profile the instants reduce to
  \`p11\` = ${KD_DEND_P11} s, \`p12\` = ${KD_DEND_P12} s and \`tstop\` =
  ${KD_DEND_TSTOP_ABS} s; on a 3b-escalated profile the same offsets land
  \`p12\` at ${KD_DENDX_P12} s and \`tstop\` at ${KD_DENDX_TSTOP_ABS} s.

$(if [ "${N_DYN:-0}" -eq 0 ]; then
cat <<NOEND

  N/A -- no step/ramp run completed (criterion 3 is NOT MEASURED in this
  record), so the END-plateau escalation had nothing to run against.
NOEND
elif [ "${N_DEND:-0}" -eq 0 ] && [ "${N_DENDFAIL:-0}" -eq 0 ]; then
cat <<NOEND

  N/A -- every step/ramp corner met the END-plateau residual-frequency
  threshold (${ACC_FERR}) inside the default ${KD_TSTOP_BASE} post-ramp hold,
  so nothing escalated and the question #255 raised does not arise here.
NOEND
elif [ "${N_DEND:-0}" -eq 0 ]; then
cat <<NOEND

  **NOT RESOLVED -- the escalation did not run.** ${N_DENDFAIL} corner(s)
  missed \`ferr_end <= ${ACC_FERR}\` and none was re-run longer
  (\`SIM_DYN_END_EXTEND=off\`, or the \`SIM_DYN_END_MAX\` budget cap).  **This
  record therefore does not say whether those corners are settling-budget
  artefacts or genuinely under-damped**, and their rows must not be read as
  either.
NOEND
else
cat <<ENDESC

  | Corner | band | hold, short | ferr_end, short | hold, long | ferr_end, long | decay ratio | single-pole expectation | classification |
  |---|---|---|---|---|---|---|---|---|
${DYN_END_TABLE}

  \`classification\`: \`settles\` = |ferr_end| came inside ${ACC_FERR} once
  given the longer hold, i.e. the short run's FAIL was a settling-budget
  artefact, the same fate criterion 1's apparent failures had on this grid
  (section 1c); \`under-damped\` = still outside ${ACC_FERR} at the longer
  hold -- genuinely marginal post-ramp damping at that operating point, not a
  measurement gap, and routed to \`sim/loop-dynamics\` (#10) rather than
  absorbed here.

  \`decay ratio\` is |ferr_end(long)| / |ferr_end(short)|; the
  \`single-pole expectation\` column beside it is what a loop settling as one
  pole at KTAU = ${KTAU} would give between those two instants.  A ratio near
  1 has not decayed at all.  **A ratio well ABOVE the expectation is worth
  reading even on a \`settles\` row**: it means the corner did converge inside
  the criterion, but far more slowly than a single pole predicts, which is a
  damping observation the bare verdict does not carry.$(
  if [ "${N_DEND_SLOW:-0}" -gt 0 ]; then printf '
  %s of the passing corner(s) decayed at least %sx slower than the single-pole
  expectation: %s.  Thinnest passing margin is %s, at ferr_end %s -- %s under
  the %s threshold, with a decay ratio of %s against an expected %s.  Both are
  stated because `settles` at that kind of margin is a pass, not a comfortable
  one, and `sim/loop-dynamics` (#10) already flags the high-`Kvco` corner as
  marginal on its own evidence.' "${N_DEND_SLOW}" "${DYN_SLOW_FACTOR}" \
    "${DEND_SLOW_LIST}" "${DEND_TIGHT}" "${DEND_TIGHT_FERR}" "${DEND_TIGHT_MARGIN}" \
    "${ACC_FERR}" "${DEND_TIGHT_DR}" "${DEND_TIGHT_DEXP}"; fi)

  **Result: ${V_DEND}.** ${N_DEND_SETTLES:-0} settled once given the longer
  hold, ${N_DEND_UNDAMPED:-0} did not: ${DEND_MARGIN_LIST:-(none)}.$(
  if [ "${N_DEND_UNDAMPED:-0}" -gt 0 ]; then printf '
  **DESIGN-MARGIN FINDING -- flagged back, not absorbed.** Worst of the
  under-damped corners is %s (band %s, ferr_end %s at the extended hold, decay
  ratio %s). At those corners the post-ramp residual is NOT a limit of the
  transient budget in this record, so it is raised against #10 (loop-dynamics
  / loop-filter margin) rather than recorded here as one more FAIL row. This
  campaign does not propose a fix; that decision belongs to #10, with its own
  evidence.' "${DEND_WORST}" "${DEND_WORST_BAND}" "${DEND_WORST_FERR}" \
    "${DEND_WORST_DR}"; fi)$(
  if [ "${N_DENDUNRESOLVED:-0}" -gt 0 ]; then printf '
  A further %s corner(s) still fail `ferr_end` and were NOT escalated (the
  `SIM_DYN_END_MAX` budget cap); those rows are unresolved, which is a
  different claim from either verdict above.' "${N_DENDUNRESOLVED}"; fi)
ENDESC
fi)

  ### 4. Power -- quiescent and dynamic, per block (criterion 4)

  Per-domain power with the loop locked at ${KFOUT} Hz, mW.

  | Bundle | Temp | settled? | core (PFD+CP+LD) @2.97/3.30/3.63 | VCO | divider | **total** |
  |---|---|---|---|---|---|---|
${PWR_TABLE}

  - Total power over the whole ${N_STEADY}-point grid: **${MNP_MW} .. ${MXP_MW} mW**
    (best ${MNP_ID}, worst **${MXP_ID}**).
  - Against the draft < ${ACC_PWR_MW} mW target: **${N_PFAIL} of ${N_STEADY}
    corners over budget** -- **${V_PWR}**.

  **Quiescent / dynamic split** (${N_SPLIT} corner(s); I(f) = I_q + k f fitted
  per domain through the ${KFOUT} Hz and ${KFOUT2} Hz locked points; power at
  3.30 V):

  | Temp | Domain | quiescent (mW) | dynamic (mW) | total (mW) | dynamic share |
  |---|---|---|---|---|---|
${SPLIT_TABLE}

  ${SPLIT_NOTE}${SPLIT_NOM}

  **Reconciliation.** The per-domain columns of the power table sum to the
  total column by construction -- the total IS vdd x (|i_core| + |i_vco| +
  |i_div|) and there is no fourth domain. What the table does **not** do is
  separate the charge pump from the PFD: they share the \`VDD\` pin, and that
  limit is stated in Methodology rather than closed with an estimate.

  ### 5. DR-002 Decision 3

  **No separate 1.8 V / 5 V supply-flavour sweep applies.** DR-002 Decision 3
  ratifies 3.3 V thick-oxide devices only for v1, so the 3.3 V +/- 10 % axis
  swept above (2.97 / 3.30 / 3.63 V) is the complete supply-axis requirement
  for v1 and this record discharges it in full.

  ### 6. Comparison against the record this one supersedes
$(if [ -z "${CMP_ID}" ]; then
cat <<'NOCMP'

  N/A -- this run was not asked to diff itself against a prior record
  (`SIM_COMPARE` unset), so no comparison is claimed here.
NOCMP
else
cat <<CMP

  **Computed, not transcribed.** The rows below are a join of THIS run's
  \`corners/${RID}/supply_steady.csv\` against the committed
  \`corners/${CMP_ID}/supply_steady.csv\`, over the corners the two runs have
  in common. The prior record's file is read and never written -- \`sim/\` is
  append-only, so \`${CMP_ID}\` stands unedited and is superseded rather than
  corrected in place.

  \`lock level\` is the design's own LOCK flag in the late window, and it is
  the column that separates **"the loop did not lock"** from **"the
  integration did not resolve the phase detector"**. A row whose \`f_out\` is
  ABOVE target while LOCK sits at ~0 V has feedback running FASTER than the
  reference with UP still asserted -- the signature \`sim/README.md\`'s
  "Closed-loop internal-timestep bound" documents for a ceiling above the PFD
  set pulse, not a design result.

  | Corner | prior tmax | verdict @${CMP_ID} | verdict now | f_out then (MHz) | f_out now (MHz) | lock then (V) | lock now (V) | flipped |
  |---|---|---|---|---|---|---|---|---|
${CMP_TABLE}

  ${CMP_SUMMARY}
CMP
fi)

  ### Overall

  | Criterion | Verdict |
  |---|---|
  | 1. output frequency vs. supply, full grid | **${V_FREQ}** |
  | 1b. control voltage inside DR-001's usable window at every corner | **${V_VCTRL}** |
  | 1c. re-runs: budget artefact vs. integration artefact vs. genuine under-damping | ${V_SETTLE} |
  | 2. static phase offset vs. supply, full grid, post-#24 CP | reported (no ratified spec line; ${N_FAIL} corner(s) outside the ${ACC_PHI_FRAC}-of-a-period lock criterion) |
  | 3. stays locked through a supply step and a supply ramp | **${V_DYN}** |
  | 3b. high-plateau re-runs: settling-budget artefact vs. genuine design-margin | ${V_DYN_SETTLE} |
  | 3c. END-plateau re-runs: settling-budget artefact vs. genuine design-margin | ${V_DEND} |
  | 4. power at ${KFOUT} Hz vs. the draft < ${ACC_PWR_MW} mW target | **${V_PWR}** |
  | 5. DR-002 Decision 3 supply-flavour scope | confirmed, no further sweep |

- **Links**:
  - Testbenches: \`sim/supply-sensitivity/testbench/tb_supply_lock.sp\`,
    \`sim/supply-sensitivity/testbench/tb_supply_dyn.sp\`
  - Runner: \`sim/supply-sensitivity/testbench/run.sh\`,
    \`sim/supply-sensitivity/testbench/report.sh\`
  - Assembly: \`sim/lib/pll_top_dut.sh\`; schematic:
    \`design/pll_top.sch\`
  - Netlist snapshots: \`sim/supply-sensitivity/netlist-snapshots/${RID}.spice\`
    (steady state), \`.../${RID}-dyn.spice\` (step/ramp)
  - Raw logs: \`sim/supply-sensitivity/corners/${RID}/\`
  - Extracted metrics: \`corners/${RID}/supply_steady.csv\`,
    \`corners/${RID}/power_split.csv\`, \`corners/${RID}/supply_dynamic.csv\`,
    \`corners/${RID}/settling_rerun.csv\`,
    \`corners/${RID}/dyn_settling_rerun.csv\` (#253),
    \`corners/${RID}/dyn_end_settling_rerun.csv\` (#255)${WAVE_LINK}
  - Cited: \`sim/vco-tuning-range/records/${CITE_VCO_RECORD}.md\` (#8, VCO
    supply pushing), \`sim/loop-dynamics/records/\` (#10, loop bandwidth and
    the passive-corner sweep), \`sim/pll-top-smoke/\` (#52, the closed-loop
    acceptance gate for this DUT -- testbench and runner only at the time of
    writing; \`sim/pll-top-smoke/records/\` is not yet minted, so nothing in
    this record rests on it)
- **Timestamp / author**: $(date -u +%Y-%m-%dT%H:%M:%SZ), ${SIM_AUTHOR:-agent-builder (issue #14)}
$(simenv_supersedes_field "${SIM_SUPERSEDES:-}")
EOF

echo "supply-sensitivity: wrote ${RECORDSDIR}/${RID}.md"
echo "supply-sensitivity: wrote ${STEADY}"
echo "supply-sensitivity: wrote ${POWER}"
echo "supply-sensitivity: wrote ${DYNCSV}"
echo "supply-sensitivity: wrote ${SETTLE}"
echo "supply-sensitivity: wrote ${DYNSETTLE}"
echo "supply-sensitivity: wrote ${DYN_END_SETTLE}"
[ "${V_FREQ}" = "PASS" ] || exit 1
exit 0
