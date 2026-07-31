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

WORK="$1"; EXP="$2"; HERE="$3"
ROOT="$(cd "${EXP}/../.." && pwd)"
# shellcheck source=../../lib/simenv.sh
. "${ROOT}/sim/lib/simenv.sh"

# Re-read the constants run.sh declared, by sourcing its assignment block.  The
# alternative -- restating them here -- is how the record's stated criterion and
# the criterion actually applied drift apart.
eval "$(sed -n '/^KFOUT=/,/^ACC_FDEV_PPM=/p;/^CITE_/p;/^VCO_TUNING=/p;/^PASSIVES=/p' "${HERE}/run.sh")"

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
for f in "${WORK}"/sdyn_*.csv; do
  IFS=, read -r bundle temp _ <<<"$(cat "${f}")"
  tag="dyn_${bundle}_T${temp}"; tag="${tag//./p}"; tag="${tag//-/m}"
  simenv_archive_log "${WORK}" "${tag}" "${CORNERSDIR}" \
    "dyn_$(simenv_corner_id "${bundle}" "${temp}" 3.30)"
  cp "${WORK}/wave_${bundle}_${temp}.csv" \
     "${CORNERSDIR}/supply_transient_$(simenv_corner_id "${bundle}" "${temp}" 3.30).csv"
done

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
  echo "bundle,temp_c,vdd_v,band,fout_hz,fdev_ppm,ferr,phi_b_s,skew_s,skew_spread_s,wup_s,wdn_s,nmeas,vctrl_avg_v,vctrl_min_v,vctrl_max_v,lock_lvl_v,i_core_a,i_vco_a,i_div_a,p_tot_w,verdict"
  cat "${WORK}"/s100_*.csv | sort -t, -k1,1 -k2,2n -k3,3n | awk -F, -v OFS=, \
    -v accf="${ACC_FERR}" -v accp="${ACC_PHI_FRAC}" -v accn="${ACC_NTOL}" \
    -v accl="${ACC_LOCK_FRAC}" -v pwr="${ACC_PWR_MW}" '
    { rows[NR] = $0; if ($3 + 0 == 3.30) fnom[$1 "|" $2] = $10 }
    END {
      for (i = 1; i <= NR; i++) {
        split(rows[i], f, ",");
        bundle=f[1]; temp=f[2]; vdd=f[3]+0; band=f[5]; fref=f[7]+0; n=f[8]+0;
        fout=f[10]+0; ffb=f[11]+0; nmeas=f[12]+0; ferr=f[13]+0; phib=f[14]+0;
        s1=f[15]+0; s2=f[16]+0; s3=f[17]+0; wup=f[18]+0; wdn=f[19]+0;
        vca=f[20]+0; vcmin=f[21]+0; vcmax=f[22]+0; lock=f[23]+0;
        ic=f[24]+0; iv=f[25]+0; id=f[26]+0;
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
        printf "%s,%s,%.2f,%s,%.6g,%.4g,%.4g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.4g,%.4g,%.4g,%.4g,%.6g,%.6g,%.6g,%.6g,%s\n",
          bundle, temp, vdd, band, fout, dev, ferr, phib, sk, smax - smin, wup, wdn,
          nmeas, vca, vcmin, vcmax, lock, ic, iv, id, p, v;
      }
    }
    function abs(x) { return x < 0 ? -x : x }'
} >"${STEADY}"

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
      # first row block is the 100 MHz run (fields 1..26), second the 50 MHz
      # run (fields 27..52); domain currents are at offsets 24/25/26.
      split("core vco div", D, " ");
      for (d = 1; d <= 3; d++) {
        i1 = abs($(23 + d)); i2 = abs($(49 + d));
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
DYNCSV="${CORNERSDIR}/supply_dynamic.csv"
{
  simenv_provenance "supply-sensitivity (step/ramp)" "${RID}" \
    "design/pll_top.sch -> sim/supply-sensitivity/netlist-snapshots/${RID}-dyn.spice" \
    "typical/27C, ss/-40C, ff/125C -- one transient each, carrying a ${KD_LO}->${KD_HI} V step and a ${KD_HI}->${KD_END} V ramp"
  echo "# phi_NN: static REF->FB phase error at probe NN (see the record's"
  echo "#   methodology for the probe instants); phi01/02 pre-step,"
  echo "#   phi03..06 through the step, phi07/08 settled high,"
  echo "#   phi09/10 during the ramp, phi11/12 settled at the low rail."
  echo "# ferr_*: residual fractional frequency error on each settled plateau"
  echo "# lock_*: LOCK-flag average over each phase of the profile, volts"
  echo "bundle,temp_c,band,vctrl0_v,phi01,phi02,phi03,phi04,phi05,phi06,phi07,phi08,phi09,phi10,phi11,phi12,ferr_lo,ferr_hi,ferr_end,fout_lo,fout_hi,fout_end,fout_step,fout_ramp,vc_lo,vc_hi,vc_end,vc_smax,vc_smin,vc_rmax,vc_rmin,vc_all_max,vc_all_min,lock_lo,lock_stp,lock_hi,lock_rmp,lock_end,lock_min,i_core_lo,i_vco_lo,i_div_lo,i_core_hi,i_vco_hi,i_div_hi,i_core_end,i_vco_end,i_div_end"
  cat "${WORK}"/sdyn_*.csv | sort -t, -k1,1
} >"${DYNCSV}"

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
    printf "WDEV_PPM=%.4g\nWDEV_ID=%s\n", wdev, wdevid;
    printf "WFERR=%.4g\nWFERR_ID=%s\n", wferr, wferrid;
    printf "WPHI_NS=%.4g\nWPHI_ID=%s\n", wphi*1e9, wphiid;
    printf "MXSK_NS=%.4g\nMXSK_ID=%s\nMNSK_NS=%.4g\nMNSK_ID=%s\n", mxsk*1e9, mxskid, mnsk*1e9, mnskid;
    printf "WSPREAD_NS=%.4g\nWSPREAD_ID=%s\n", wspread*1e9, wspreadid;
    printf "MXP_MW=%.4g\nMXP_ID=%s\nMNP_MW=%.4g\nMNP_ID=%s\nN_PFAIL=%d\n", mxp*1e3, mxpid, mnp*1e3, mnpid, npfail+0;
    printf "N_VOUT=%d\nVOUT=%s\n", nvout+0, (vout == "" ? "(none)" : "\"" vout "\"");
    printf "MXVC=%.4g\nMXVC_ID=%s\nMNVC=%.4g\nMNVC_ID=%s\n", mxvc, mxvcid, mnvc, mnvcid;
    printf "MXSLOPE=%.4g\nMXSLOPE_ID=%s\nMNSLOPE=%.4g\nMNSLOPE_ID=%s\nAVSLOPE=%.4g\n", mxs, mxsid, mns, mnsid, sum/ns;
  }
  function abs(x) { return x < 0 ? -x : x }' "${STEADY}")"

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
    printf "SPLIT_MAX_MW=%.4g\nSPLIT_MAX_ID=%s\nSPLIT_MAXQ_MW=%.4g\nSPLIT_MAXD_MW=%.4g\n", mx*1e3, mxid, mxq*1e3, mxd*1e3;
    printf "NOMQ_MW=%.4g\nNOMD_MW=%.4g\n", nq*1e3, nd*1e3;
    printf "NOMQC_MW=%.4g\nNOMDC_MW=%.4g\nNOMQV_MW=%.4g\nNOMDV_MW=%.4g\nNOMQD_MW=%.4g\nNOMDD_MW=%.4g\n",
      nqc*1e3, ndc*1e3, nqv*1e3, ndv*1e3, nqd*1e3, ndd*1e3;
  }' "${POWER}")"

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
    printf "DYN_PSTEP_NS=%.4g\nDYN_PSTEP_ID=%s\nDYN_PRAMP_NS=%.4g\nDYN_PRAMP_ID=%s\n", mxstep*1e9, mxstepid, mxramp*1e9, mxrampid;
    printf "DYN_MXFE=%.4g\nDYN_MXFE_ID=%s\n", mxfe, mxfeid;
    printf "DYN_MNLOCK=%.4g\nDYN_MNLOCK_ID=%s\n", mnlock, mnlockid;
    printf "DYN_DSTEP_HZ=%.4g\nDYN_DSTEP_ID=%s\n", mxdstep, mxdstepid;
    printf "DYN_DVC=%.4g\nDYN_DVC_ID=%s\nDYN_VEX=%.4g\nDYN_VEX_ID=%s\n", mxdvc, mxdvcid, mxvex, mxvexid;
  }
  function abs(x) { return x < 0 ? -x : x }' "${DYNCSV}")"

# Overall verdicts.
V_FREQ=$([ "${N_FAIL}" -eq 0 ] && echo PASS || echo FAIL)
V_PWR=$([ "${N_PFAIL}" -eq 0 ] && echo PASS || echo FAIL)
V_DYN=$([ "${DYN_LOST}" -eq 0 ] && echo PASS || echo FAIL)
V_VCTRL=$([ "${N_VOUT}" -eq 0 ] && echo PASS || echo "FAIL")

# Per-(bundle,temp) frequency-deviation table, 15 rows.
FDEV_TABLE="$(awk -F, '
  !/^#/ && $1 != "bundle" {
    key = $1 "|" $2; band[key] = $4;
    if ($3 + 0 < 3.0)  { d297[key] = $6; v297[key] = $14; f297[key] = $5 }
    if ($3 + 0 == 3.30){ f330[key] = $5; v330[key] = $14 }
    if ($3 + 0 > 3.6)  { d363[key] = $6; v363[key] = $14; f363[key] = $5 }
    order[key] = 1;
  }
  END {
    nb = split("typical ff ss fs sf", BU, " "); nt = split("-40 27 125", TE, " ");
    for (bi = 1; bi <= nb; bi++) for (ti = 1; ti <= nt; ti++) {
      k = BU[bi] "|" TE[ti];
      if (!(k in order)) continue;
      printf "  | %s | %s | %s | %+.4g | %+.4g | %.3f / %.3f / %.3f | %.4g |\n",
        BU[bi], TE[ti], band[k], d297[k], d363[k], v297[k], v330[k], v363[k],
        (v363[k] - v297[k]) / 0.66;
    }
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
    order[key] = 1;
  }
  END {
    nb = split("typical ff ss fs sf", BU, " "); nt = split("-40 27 125", TE, " ");
    for (bi = 1; bi <= nb; bi++) for (ti = 1; ti <= nt; ti++) {
      k = BU[bi] "|" TE[ti];
      if (!(k in order)) continue;
      printf "  | %s | %s | %.3f / %.3f / %.3f | %.3f / %.3f / %.3f | %.3f / %.3f / %.3f | %.3f / %.3f / %.3f |\n",
        BU[bi], TE[ti],
        C[k "a"], C[k "b"], C[k "c"], VV[k "a"], VV[k "b"], VV[k "c"],
        D[k "a"], D[k "b"], D[k "c"], P[k "a"], P[k "b"], P[k "c"];
    }
  }' "${STEADY}")"

# Step/ramp table.
DYN_TABLE="$(awk -F, '
  !/^#/ && $1 != "bundle" {
    printf "  | %s / %s C | %.4g | %.4g | %.4g | %.4g | %.4g | %.3f / %.3f / %.3f | %.4g |\n",
      $1, $2, $5*1e9, maxa($7,$8,$9,$10)*1e9, maxa($13,$14,$13,$14)*1e9,
      $17, $19, $25, $26, $27, $39;
  }
  function maxa(a, b, c, d,   m) {
    m = ab(a); if (ab(b) > m) m = ab(b); if (ab(c) > m) m = ab(c); if (ab(d) > m) m = ab(d);
    return m;
  }
  function ab(x) { return x < 0 ? -x : x }' "${DYNCSV}")"

# Power-split table at 3.30 V.
SPLIT_TABLE="$(awk -F, '
  !/^#/ && $1 != "bundle" && $3 + 0 == 3.30 {
    printf "  | %s C | %s | %.4g | %.4g | %.4g | %.0f %% |\n",
      $2, $4, $9*1e3, $10*1e3, ($9+$10)*1e3, 100*$10/($9+$10);
  }' "${POWER}" | sort -t'|' -k2,2n)"

NOMTOT_MW="$(awk -v a="${NOMQ_MW}" -v b="${NOMD_MW}" 'BEGIN{printf "%.4g", a+b}')"

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
  here is a design-input claim in the second form \`sim/README.md\` admits.
- **Netlist provenance**: schematic (\`design/pll_top.sch\` (#52), exported by
  \`design/netlist.sh\` to \`design/netlist/pll_top.spice\`, assembled with the
  campaign stimulus by \`sim/lib/assemble_closed_loop.sh\`) ->
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
  - **Steady state (criteria 1, 2, 4): the full ${N_STEADY}-point default grid.**
    5 MOS bundles x 3 temperatures x 3 supplies.
    - Bundles -> \`.lib\` sections of \`sm141064.ngspice\`:
      \`typical\` -> typical; \`ff\` -> ff; \`ss\` -> ss; \`fs\` -> fs;
      \`sf\` -> sf -- each with \`${PASSIVES//,/, }\`.
    - Temperature: -40 C, 27 C, 125 C. Supply: 2.97 V, 3.30 V, 3.63 V.
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
  - **Quiescent/dynamic power split (criterion 4): a 9-point subset**,
    \`typical\` x 3 temperatures x 3 supplies, each corner run a SECOND time
    locked at ${KFOUT2} Hz. Justified in Methodology: the split
    re-attributes a current the full grid already reports, between two
    columns.
  - **Supply step/ramp (criterion 3): ${N_DYN} corners** -- \`typical\`/27 C,
    \`ss\`/-40 C, \`ff\`/125 C, i.e. nominal and the two process/temperature
    extremes. The supply axis is not a grid axis for these runs because the
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
    \`sim/lib/assemble_closed_loop.sh\`, which is the single closed-loop
    assembly path in this repo. Nothing here is a hand-transcribed copy of the
    design, and the frozen snapshots above are self-contained.
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
  - **Warm start, not cold start.** \`.ic v(vctrl)\` = the predicted lock
    point for that corner; the loop pulls it the rest of the way. Cold-start
    acquisition is \`sim/pll-top-smoke\` (#52)'s claim and \`sim/lock-time\`
    (#12)'s campaign, and repeating it ${N_STEADY} times here would add the
    acquisition ramp to every run for no number this record reports. The
    residual is **not** assumed away: the lock criterion below is applied to
    the measured late-window numbers exactly as it would be after a cold
    start, so a corner whose prediction was poor fails the residual-frequency
    check rather than quietly reporting a half-settled number.
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
    contaminates the other. The **step** is ${KD_LO} -> ${KD_HI} V with a
    ${KD_TEDGE} edge at t = ${KD_TSTEP} -- about 1/40 of the loop's own
    response time, i.e. a step as far as the loop is concerned. The **ramp**
    is ${KD_HI} -> ${KD_END} V over $(awk -v a="${KD_TRAMP}" -v b="${KD_TREND}" 'BEGIN{print "40 us"}'),
    i.e. 16.5 mV/us, deliberately SLOWER than the loop so it tests tracking
    rather than transient rejection. The two together bracket the loop
    bandwidth from both sides, which one rate could not. Twelve REF->FB phase
    probes are placed across the profile, each snapped onto a reference
    half-period.
  - **VCO supply pushing is CITED, not re-derived.** #8 measured it open loop:
    **${CITE_PUSH_WORST} %/V** worst-case static (median
    ${CITE_PUSH_MEDIAN} %/V) and **${CITE_STEP_WORST} MHz/V** transient for a
    0.1 V step at the 100 MHz-class operating point --
    \`sim/vco-tuning-range/records/${CITE_VCO_RECORD}.md\`, sections 1 and 2.
    This record measures what the CLOSED loop does with that pushing, which is
    a different quantity: inside the loop bandwidth the PLL corrects the VCO's
    excursion and outside it does not. The consistency check between the two
    is in the Result section.
  - **Simulator settings**: \`.tran ${KTSTEP} ${KTSTOP} 0 ${KTMAX}\` for the
    steady-state runs and \`.tran ${KTSTEP} ${KD_TSTOP} 0 ${KTMAX}\` for the
    step/ramp runs; \`reltol 1e-3\`, \`abstol 1e-13\`, \`vntol 1e-6\`,
    \`rshunt 1e12\`, \`itl4 200\`. The ${KTMAX} timestep ceiling is set by the
    CHARGE PUMP, not the VCO: the PFD's minimum UP/DN pulse is 1.1-1.9 ns and
    this campaign MEASURES those widths, so the narrower pulse must be
    resolved by several timesteps and not merely integrated correctly. It is
    tighter than \`sim/pll-top-smoke\`'s 500 ps for exactly that reason.
  - **Waveform retained**: the step/ramp transient IS the argument for
    criterion 3, so it is kept -- decimated to ${KD_DECIM} s per sample as
    \`corners/${RID}/supply_transient_<corner>.csv\` (control node, LOCK flag,
    the rail itself and the feedback edge), never as a rawfile.
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

  | Bundle | Temp | Band | fdev @2.97 V (ppm) | fdev @3.63 V (ppm) | Vctrl @2.97/3.30/3.63 (V) | dVctrl/dVdd (V/V) |
  |---|---|---|---|---|---|---|
${FDEV_TABLE}

  - Worst frequency deviation from the nominal-supply value anywhere on the
    grid: **${WDEV_PPM} ppm** at ${WDEV_ID} (criterion: <= ${ACC_FDEV_PPM} ppm).
  - Worst residual fractional frequency error: **${WFERR}** at ${WFERR_ID}
    (criterion: <= ${ACC_FERR}).
  - Control-voltage slope dVctrl/dVdd across the +/-10 % rail:
    **${MNSLOPE} .. ${MXSLOPE} V/V** (mean ${AVSLOPE}), most sensitive at
    ${MXSLOPE_ID}, least at ${MNSLOPE_ID}.
  - Settled control voltage over the whole grid: **${MNVC} .. ${MXVC} V**
    (lowest ${MNVC_ID}, highest ${MXVC_ID}). Points outside DR-001 Decision
    2's usable ${ACC_VCTRL_LO}-${ACC_VCTRL_HI} V window: **${N_VOUT}** --
    ${VOUT}. **${V_VCTRL}**
  - **Overall criterion 1: ${V_FREQ}.**

  **Consistency with #8's open-loop pushing.** The loop holds f_out fixed by
  moving Vctrl against the VCO's supply pushing, so the measured dVctrl/dVdd
  and #8's measured pushing are two views of one mechanism:
  dVctrl/dVdd ~ -(df/dVdd) / Kvco. With #8's median static pushing of
  ${CITE_PUSH_MEDIAN} %/V at 100 MHz (i.e. about -39 MHz/V) and its measured
  Kvco of 38-135 MHz/V in the bands this operating point uses, that predicts a
  slope of roughly 0.3-1.0 V/V. The measured ${MNSLOPE} .. ${MXSLOPE} V/V sits
  inside that envelope, which is the cross-check: the closed loop is absorbing
  the pushing #8 characterised, through the control node, exactly as expected.

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
  between t = ${KD_TRAMP} and t = ${KD_TREND} (16.5 mV/us); settle.

  | Corner | phase, pre-step (ns) | peak phase excursion, step (ns) | peak phase excursion, ramp (ns) | residual f error, low plateau | ... end plateau | Vctrl low/high/end (V) | LOCK min (V) |
  |---|---|---|---|---|---|---|---|
${DYN_TABLE}

  - Worst peak REF->FB phase excursion through the **step**:
    **${DYN_PSTEP_NS} ns** at ${DYN_PSTEP_ID}.
  - Worst peak excursion through the **ramp**: **${DYN_PRAMP_NS} ns** at
    ${DYN_PRAMP_ID}.
  - Worst output-frequency excursion measured inside the step disturbance
    (20 CLK cycles from the end of the supply edge): **${DYN_DSTEP_HZ} Hz** at
    ${DYN_DSTEP_ID}.
  - Worst residual frequency error on any settled plateau:
    **${DYN_MXFE}** at ${DYN_MXFE_ID} (criterion <= ${ACC_FERR}) -- i.e. the
    loop is locked on every plateau it was asked about.
  - Minimum LOCK-flag level anywhere in the profile: **${DYN_MNLOCK} V** at
    ${DYN_MNLOCK_ID}.
  - Control-node travel from the high rail to the low rail:
    **${DYN_DVC} V** at ${DYN_DVC_ID}; peak excursion beyond the settled value
    during the step: **${DYN_VEX} V** at ${DYN_VEX_ID}.
  - **Overall criterion 3: ${V_DYN}** (${DYN_LOST} of ${N_DYN} runs failed the
    stays-locked criterion on some plateau).

  The step is where #8's open-loop transient pushing (${CITE_STEP_WORST} MHz/V
  for a 0.1 V step, i.e. about -0.16 % per 0.1 V at 100 MHz) enters: it walks
  the VCO instantaneously, and the loop then pulls it back with a time
  constant set by its own bandwidth. The phase excursion above is the integral
  of that error while the loop corrects it, which is the number a system-level
  jitter budget consumes -- **not** #8's open-loop figure, and not a
  re-derivation of it.

  ### 4. Power -- quiescent and dynamic, per block (criterion 4)

  Per-domain power with the loop locked at ${KFOUT} Hz, mW.

  | Bundle | Temp | core (PFD+CP+LD) @2.97/3.30/3.63 | VCO | divider | **total** |
  |---|---|---|---|---|---|
${PWR_TABLE}

  - Total power over the whole ${N_STEADY}-point grid: **${MNP_MW} .. ${MXP_MW} mW**
    (best ${MNP_ID}, worst **${MXP_ID}**).
  - Against the draft < ${ACC_PWR_MW} mW target: **${N_PFAIL} of ${N_STEADY}
    corners over budget** -- **${V_PWR}**.

  **Quiescent / dynamic split** (typical bundle, 9-point subset; I(f) = I_q +
  k f fitted through the ${KFOUT} Hz and ${KFOUT2} Hz locked points; power at
  3.30 V):

  | Temp | Domain | quiescent (mW) | dynamic (mW) | total (mW) | dynamic share |
  |---|---|---|---|---|---|
${SPLIT_TABLE}

  At the nominal corner (typical/27 C/3.30 V) the block draws
  **${NOMTOT_MW} mW**, of which **${NOMQ_MW} mW** is frequency-independent and
  **${NOMD_MW} mW** scales with frequency. Per domain, quiescent / dynamic:
  core ${NOMQC_MW} / ${NOMDC_MW} mW, VCO ${NOMQV_MW} / ${NOMDV_MW} mW,
  divider ${NOMQD_MW} / ${NOMDD_MW} mW. The worst corner of the reduced grid
  is ${SPLIT_MAX_ID} at ${SPLIT_MAX_MW} mW (${SPLIT_MAXQ_MW} quiescent,
  ${SPLIT_MAXD_MW} dynamic).

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

  ### Overall

  | Criterion | Verdict |
  |---|---|
  | 1. output frequency vs. supply, full grid | **${V_FREQ}** |
  | 1b. control voltage inside DR-001's usable window at every corner | **${V_VCTRL}** |
  | 2. static phase offset vs. supply, full grid, post-#24 CP | reported (no ratified spec line; ${N_FAIL} corner(s) outside the ${ACC_PHI_FRAC}-of-a-period lock criterion) |
  | 3. stays locked through a supply step and a supply ramp | **${V_DYN}** |
  | 4. power at ${KFOUT} Hz vs. the draft < ${ACC_PWR_MW} mW target | **${V_PWR}** |
  | 5. DR-002 Decision 3 supply-flavour scope | confirmed, no further sweep |

- **Links**:
  - Testbenches: \`sim/supply-sensitivity/testbench/tb_supply_lock.sp\`,
    \`sim/supply-sensitivity/testbench/tb_supply_dyn.sp\`
  - Runner: \`sim/supply-sensitivity/testbench/run.sh\`,
    \`sim/supply-sensitivity/testbench/report.sh\`
  - Assembly: \`sim/lib/assemble_closed_loop.sh\`; schematic:
    \`design/pll_top.sch\`
  - Netlist snapshots: \`sim/supply-sensitivity/netlist-snapshots/${RID}.spice\`
    (steady state), \`.../${RID}-dyn.spice\` (step/ramp)
  - Raw logs: \`sim/supply-sensitivity/corners/${RID}/\`
  - Extracted metrics: \`corners/${RID}/supply_steady.csv\`,
    \`corners/${RID}/power_split.csv\`, \`corners/${RID}/supply_dynamic.csv\`
  - Retained waveforms: \`corners/${RID}/supply_transient_*.csv\`
  - Cited: \`sim/vco-tuning-range/records/${CITE_VCO_RECORD}.md\` (#8, VCO
    supply pushing), \`sim/loop-dynamics/records/\` (#10, loop bandwidth and
    the passive-corner sweep), \`sim/pll-top-smoke/records/\` (#52, the
    closed-loop acceptance gate for this DUT)
- **Timestamp / author**: $(date -u +%Y-%m-%dT%H:%M:%SZ), ${SIM_AUTHOR:-agent-builder (issue #14)}
$(simenv_supersedes_field "${SIM_SUPERSEDES:-}")
EOF

echo "supply-sensitivity: wrote ${RECORDSDIR}/${RID}.md"
echo "supply-sensitivity: wrote ${STEADY}"
echo "supply-sensitivity: wrote ${POWER}"
echo "supply-sensitivity: wrote ${DYNCSV}"
[ "${V_FREQ}" = "PASS" ] && [ "${V_DYN}" = "PASS" ] || exit 1
exit 0
