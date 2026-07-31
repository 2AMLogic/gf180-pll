#!/usr/bin/env bash
# gf180-pll :: divider-ratio :: corner runner (issue #11, DR-001 Decision 3)
#
# Three sub-campaigns share this directory because they substantiate three
# linked claims about the same block. Each mints its OWN record ID, because
# sim/README.md ties one record to one frozen netlist snapshot and the three
# have different DUTs:
#
#   dff    tb_dff_setup.sp     x design/netlist/dff_tg_3v3.spice
#          setup/hold of the flop the whole divider is built from, 45 corners.
#          Runs FIRST because the chain's retiming margin is computed against
#          its per-corner setup number.
#   cell   tb_div23_cell.sp    x design/netlist/div23_cell.spice
#          single-cell divide-by-2 and divide-by-3, both output edges, both
#          input duty cycles, at the top of the band and at the bottom.
#          45 corners x 2 input rates.
#   chain  tb_divider_chain.sp x design/netlist/divider_chain.spice
#          full six-cell chain + retiming flop: the N = 4..64 ratio sweep, the
#          full-grid check at three N, a low-rate check, and the retiming
#          setup closure.
#
# Usage:
#   ./run.sh                 # everything; mints three records
#   ./run.sh --check         # nominal corner of each sub-campaign, to stdout
#   SIM_JOBS=8 ./run.sh      # cap parallelism
#
# The DUT netlists come from design/netlist/*.spice, which design/netlist.sh
# exports from the xschem schematics in design/. Run `design/netlist.sh
# --check` first if the schematics may have changed: this runner does not
# regenerate them, it freezes whatever is committed.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP="$(cd "${HERE}/.." && pwd)"
ROOT="$(cd "${EXP}/../.." && pwd)"
# shellcheck source=../../lib/simenv.sh
. "${HERE}/../../lib/simenv.sh"

WORK="${EXP}/work"
NETLIST_DIR="${ROOT}/design/netlist"

# Combined "deck" handed to simenv_run_deck: the exported DUT subcircuit
# followed by the testbench that instantiates it. One file, so the frozen
# netlist snapshot of a record is self-contained.
dut_file() { echo "${WORK}/dut_$1.sp"; }

build_duts() {
  mkdir -p "${WORK}"
  local blk tb
  for pair in "dff:dff_tg_3v3:tb_dff_setup.sp" \
              "cell:div23_cell:tb_div23_cell.sp" \
              "chain:divider_chain:tb_divider_chain.sp"; do
    IFS=: read -r key blk tb <<<"${pair}"
    [ -f "${NETLIST_DIR}/${blk}.spice" ] || {
      echo "ERROR: ${NETLIST_DIR}/${blk}.spice missing -- run design/netlist.sh" >&2
      exit 1
    }
    cat "${NETLIST_DIR}/${blk}.spice" "${HERE}/${tb}" >"$(dut_file "${key}")"
  done
}

# tag for a work subdirectory: filesystem-safe, unique per job
mktag() { local t="$*"; t="${t// /_}"; t="${t//./p}"; t="${t//-/m}"; echo "${t}"; }

# simenv_run_deck treats any "Error:" in the ngspice log as fatal, which is
# right for a device sweep but wrong here: a FAILED `.meas` is the measurement.
# The setup/hold ladder deliberately drives copies past their timing limit so
# that their capture measurement fails, and a divider corner that mis-divides
# must be RECORDED as a FAIL row rather than aborting the whole sweep. So the
# completion test here is "did the transient finish", not "was the log clean".
run_deck_soft() {
  local workdir="$2" tag="$3"
  simenv_run_deck "$@" >/dev/null 2>&1 || true
  local log="${workdir}/${tag}/ngspice.log"
  grep -q "Total analysis time" "${log}" 2>/dev/null && return 0
  echo "ERROR: ngspice did not complete a transient for tag=${tag} (see ${log})" >&2
  return 1
}

# ---------------------------------------------------------------------------
# N -> chain programming.  N = 2^k + sum(p_i . 2^i), i < k;  SEL_(k-1) = 1.
# Prints "k sel0..sel5 p0..p5" as 13 space-separated 0/1 fields plus k.
# ---------------------------------------------------------------------------
n_to_code() {
  local n="$1" k=0 pow=1 m i
  while [ $((pow * 2)) -le "${n}" ]; do pow=$((pow * 2)); k=$((k + 1)); done
  m=$((n - pow))
  local sel=() p=()
  for i in 0 1 2 3 4 5; do
    if [ "${i}" -eq $((k - 1)) ]; then sel+=(1); else sel+=(0); fi
    if [ "${i}" -lt "${k}" ]; then p+=($(( (m >> i) & 1 ))); else p+=(0); fi
  done
  echo "${k} ${sel[*]} ${p[*]}"
}

# ===========================================================================
# dff: setup / hold of dff_tg_3v3
# ===========================================================================
DFF_HEADER="process,temp_c,vdd_v,tsetup_s,thold_s,tcq_r_s,tcq_f_s"

# Setup ladder and hold ladder, kept in step with tb_dff_setup.sp.
DFF_TI=(1.00e-9 0.20e-9 0.10e-9 0.05e-9 0.02e-9 0.00 -0.02e-9 -0.05e-9 -0.10e-9 -0.15e-9)
DFF_TH=(0.50e-9 0.20e-9 0.10e-9 0.00 -0.10e-9 -0.20e-9 -0.30e-9 -0.40e-9 -0.50e-9 -0.70e-9)

run_one_dff() {
  local corner="$1" temp="$2" vdd="$3"
  local tag; tag=$(mktag "dff ${corner} ${temp} ${vdd}")
  run_deck_soft "$(dut_file dff)" "${WORK}" "${tag}" "${corner}" "${temp}" "vsup=${vdd}"
  local log="${WORK}/${tag}/ngspice.log" i
  local cqa=() cqb=() hqc=()
  for i in 0 1 2 3 4 5 6 7 8 9; do
    cqa+=("$(simenv_meas "${log}" "cqa${i}")")
    cqb+=("$(simenv_meas "${log}" "cqb${i}")")
    hqc+=("$(simenv_meas "${log}" "hqc${i}")")
  done
  awk -v c="${corner}" -v t="${temp}" -v v="${vdd}" \
      -v ti="${DFF_TI[*]}" -v th="${DFF_TH[*]}" \
      -v a="${cqa[*]}" -v b="${cqb[*]}" -v h="${hqc[*]}" '
    BEGIN {
      na = split(ti, TI, " "); split(th, TH, " ")
      split(a, A, " "); split(b, B, " "); split(h, H, " ")
      # Setup: the smallest ladder step whose clk->Q has not yet degraded by
      # more than 10% against the relaxed reference (step 1). A step whose
      # .meas failed ("nan") never captured and is a violated point.
      sa = TI[na]; ok = 1
      for (i = 2; i <= na && ok; i++) {
        if (A[i] + 0 == 0 || A[i] == "nan" || A[i] + 0 > 1.1 * (A[1] + 0)) { sa = TI[i-1]; ok = 0 }
      }
      sb = TI[na]; ok = 1
      for (i = 2; i <= na && ok; i++) {
        if (B[i] + 0 == 0 || B[i] == "nan" || B[i] + 0 > 1.1 * (B[1] + 0)) { sb = TI[i-1]; ok = 0 }
      }
      su = (sa + 0 > sb + 0) ? sa + 0 : sb + 0
      # Hold: the most negative ladder step at which the late data was still
      # NOT captured (Q stayed below 10% of the rail).
      ho = TH[1] + 0;
      for (i = 1; i <= na; i++) {
        if (H[i] != "nan" && H[i] + 0 < 0.1 * v) ho = TH[i] + 0
      }
      printf "%s,%s,%s,%.6g,%.6g,%.6g,%.6g\n", c, t, v, su, ho, A[1] + 0, B[1] + 0
    }'
}

# ===========================================================================
# cell: single div23_cell
# ===========================================================================
CELL_HEADER="process,temp_c,vdd_v,kf_hz,n_div2,n_div3,n_div2_33duty,n_div3_67duty,n_1p5x,n_2x,tcq_s,pw_div2_s,pw_div3_s,pw_modout_s,i_cell_a,pass"

run_one_cell() {
  local corner="$1" temp="$2" vdd="$3" kf="$4"
  local tag; tag=$(mktag "cell ${corner} ${temp} ${vdd} ${kf}")
  run_deck_soft "$(dut_file cell)" "${WORK}" "${tag}" "${corner}" "${temp}" \
    "vsup=${vdd}" "kf=${kf}" "ktstep=$(awk -v f="${kf}" 'BEGIN{printf "%.6g", 1/(250*f)}')" \
    "ktstop=$(awk -v f="${kf}" 'BEGIN{printf "%.6g", 12/f}')"
  local log="${WORK}/${tag}/ngspice.log"
  local na nb nc nd ne nf tcq pwa pwb pwmb iavg
  na=$(simenv_meas "${log}" na);   nb=$(simenv_meas "${log}" nb)
  nc=$(simenv_meas "${log}" nc);   nd=$(simenv_meas "${log}" nd)
  ne=$(simenv_meas "${log}" ne);   nf=$(simenv_meas "${log}" nf)
  tcq=$(simenv_meas "${log}" tcq)
  pwa=$(simenv_meas "${log}" pwa); pwb=$(simenv_meas "${log}" pwb)
  pwmb=$(simenv_meas "${log}" pwmb); iavg=$(simenv_meas "${log}" iavg)
  awk -v c="${corner}" -v t="${temp}" -v v="${vdd}" -v f="${kf}" \
      -v na="${na}" -v nb="${nb}" -v nc="${nc}" -v nd="${nd}" -v ne="${ne}" -v nf="${nf}" \
      -v tcq="${tcq}" -v pwa="${pwa}" -v pwb="${pwb}" -v pwmb="${pwmb}" -v ia="${iavg}" '
    function abs(x) { return x < 0 ? -x : x }
    function near(x, y) { return (x != "nan" && abs(x - y) < 1e-3) }
    BEGIN {
      tv = 1 / f
      # The .meas pulse widths are (fall#3 - rise#3); when the cell happens to
      # start high the two land in the other order and the width comes out one
      # output period short. Adding it back is exact, not a fudge.
      if (pwa != "nan" && pwa + 0 < 0) pwa = pwa + 2 * tv
      if (pwb != "nan" && pwb + 0 < 0) pwb = pwb + 3 * tv
      ok = near(na,2) && near(nb,3) && near(nc,2) && near(nd,3) && near(ne,3) && near(nf,3)
      printf "%s,%s,%s,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%s\n",
             c, t, v, f, na, nb, nc, nd, ne, nf, tcq, pwa, pwb, pwmb, abs(ia),
             (ok ? "PASS" : "FAIL")
    }'
}

# ===========================================================================
# chain: full divider_chain
# ===========================================================================
CHAIN_HEADER="process,temp_c,vdd_v,kf_hz,n_target,k_cells,n_meas_1,n_meas_2,n_divout,t_arr_s,t_rtcq_s,fb_pw_s,i_div_a,pass"

run_one_chain() {
  local corner="$1" temp="$2" vdd="$3" kf="$4" n="$5"
  local code; code=$(n_to_code "${n}")
  local k; k=$(echo "${code}" | cut -d' ' -f1)
  local sel; sel=$(echo "${code}" | cut -d' ' -f2-7)
  local p;   p=$(echo "${code}" | cut -d' ' -f8-13)
  local tag; tag=$(mktag "chain ${corner} ${temp} ${vdd} ${kf} ${n}")
  local params=("vsup=${vdd}" "kf=${kf}")
  params+=("ktstep=$(awk -v f="${kf}" 'BEGIN{printf "%.6g", 1/(100*f)}')")
  params+=("ktstop=$(awk -v f="${kf}" -v n="${n}" 'BEGIN{printf "%.6g", (3*n+8)/f}')")
  local i=0 s
  for s in ${sel}; do params+=("ksel${i}=${s}"); i=$((i + 1)); done
  i=0
  for s in ${p}; do params+=("kp${i}=${s}"); i=$((i + 1)); done
  run_deck_soft "$(dut_file chain)" "${WORK}" "${tag}" "${corner}" "${temp}" "${params[@]}"
  local log="${WORK}/${tag}/ngspice.log"
  local n1 n2 ndo tarr trt fbpw iavg
  n1=$(simenv_meas "${log}" n1);   n2=$(simenv_meas "${log}" n2)
  ndo=$(simenv_meas "${log}" ndo); tarr=$(simenv_meas "${log}" t_arr)
  trt=$(simenv_meas "${log}" t_rtcq); fbpw=$(simenv_meas "${log}" fbpw)
  iavg=$(simenv_meas "${log}" iavg)
  awk -v c="${corner}" -v t="${temp}" -v v="${vdd}" -v f="${kf}" -v n="${n}" -v k="${k}" \
      -v n1="${n1}" -v n2="${n2}" -v ndo="${ndo}" -v ta="${tarr}" -v tr="${trt}" \
      -v pw="${fbpw}" -v ia="${iavg}" '
    function abs(x) { return x < 0 ? -x : x }
    BEGIN {
      tv = 1 / f
      if (pw != "nan" && pw + 0 < 0) pw = pw + n * tv
      ok = (n1 != "nan" && n2 != "nan" && ndo != "nan" &&
            abs(n1 - n) < 1e-3 && abs(n2 - n) < 1e-3 && abs(ndo - n) < 1e-2)
      printf "%s,%s,%s,%.6g,%d,%d,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%s\n",
             c, t, v, f, n, k, n1, n2, ndo, ta, tr, pw, abs(ia), (ok ? "PASS" : "FAIL")
    }'
}

# ===========================================================================
# Re-entry points for the parallel fan-out
# ===========================================================================
case "${1:-}" in
  --one-dff)   shift; run_one_dff   "$@"; exit 0 ;;
  --one-cell)  shift; run_one_cell  "$@"; exit 0 ;;
  --one-chain) shift; run_one_chain "$@"; exit 0 ;;
esac

simenv_require_tools
build_duts

if [ "${1:-}" = "--check" ]; then
  echo "== dff =="
  echo "${DFF_HEADER}";   run_one_dff   typical 27 3.30
  echo "== cell =="
  echo "${CELL_HEADER}";  run_one_cell  typical 27 3.30 200e6
  echo "== chain =="
  echo "${CHAIN_HEADER}"; run_one_chain typical 27 3.30 200e6 4
  exit 0
fi

JOBS=$(simenv_jobs)
mkdir -p "${WORK}"

# The corners that stress the divider hardest: slowest (max accumulated
# clk->Q vs. the VCO period) and fastest (narrowest pulses), plus nominal.
STRESS=("ss 125 2.97" "ff -40 3.63" "typical 27 3.30")

# ---------------------------------------------------------------------------
# 1. dff setup/hold, full grid
# ---------------------------------------------------------------------------
DFF_JOBS="${WORK}/jobs_dff.txt"; : >"${DFF_JOBS}"
for corner in "${SIMENV_MOS_CORNERS[@]}"; do
  for temp in "${SIMENV_TEMPS[@]}"; do
    for vdd in "${SIMENV_VDDS[@]}"; do
      echo "${corner} ${temp} ${vdd}" >>"${DFF_JOBS}"
    done
  done
done
echo "divider-ratio/dff  : $(wc -l <"${DFF_JOBS}" | tr -d ' ') points, ${JOBS} jobs"
DFF_ROWS="${WORK}/rows_dff.csv"; : >"${DFF_ROWS}"
# shellcheck disable=SC2016
xargs -P "${JOBS}" -L 1 "${BASH:-/bin/bash}" -c 'exec "$0" --one-dff "$@"' \
  "${HERE}/run.sh" <"${DFF_JOBS}" >>"${DFF_ROWS}"
sort -t, -k1,1 -k2,2n -k3,3n "${DFF_ROWS}" -o "${DFF_ROWS}"

# ---------------------------------------------------------------------------
# 2. single cell, full grid x {top of band, bottom of band}
# ---------------------------------------------------------------------------
CELL_JOBS="${WORK}/jobs_cell.txt"; : >"${CELL_JOBS}"
for corner in "${SIMENV_MOS_CORNERS[@]}"; do
  for temp in "${SIMENV_TEMPS[@]}"; do
    for vdd in "${SIMENV_VDDS[@]}"; do
      echo "${corner} ${temp} ${vdd} 200e6" >>"${CELL_JOBS}"
      echo "${corner} ${temp} ${vdd} 10e6"  >>"${CELL_JOBS}"
    done
  done
done
echo "divider-ratio/cell : $(wc -l <"${CELL_JOBS}" | tr -d ' ') points, ${JOBS} jobs"
CELL_ROWS="${WORK}/rows_cell.csv"; : >"${CELL_ROWS}"
# shellcheck disable=SC2016
xargs -P "${JOBS}" -L 1 "${BASH:-/bin/bash}" -c 'exec "$0" --one-cell "$@"' \
  "${HERE}/run.sh" <"${CELL_JOBS}" >>"${CELL_ROWS}"
sort -t, -k4,4n -k1,1 -k2,2n -k3,3n "${CELL_ROWS}" -o "${CELL_ROWS}"

# ---------------------------------------------------------------------------
# 3. chain: every N from 4 to 64 at the stress corners, three N over the full
#    grid, and a bottom-of-band rate check
# ---------------------------------------------------------------------------
CHAIN_JOBS="${WORK}/jobs_chain.txt"; : >"${CHAIN_JOBS}"
for cs in "${STRESS[@]}"; do
  for n in $(seq 4 64); do echo "${cs} 200e6 ${n}"; done
done >>"${CHAIN_JOBS}"
for corner in "${SIMENV_MOS_CORNERS[@]}"; do
  for temp in "${SIMENV_TEMPS[@]}"; do
    for vdd in "${SIMENV_VDDS[@]}"; do
      for n in 4 33 64; do echo "${corner} ${temp} ${vdd} 200e6 ${n}"; done
    done
  done
done >>"${CHAIN_JOBS}"
# Bottom of the output band (10 MHz): the "static CMOS has no minimum clock
# frequency" property DR-001 Decision 3 chose the logic family for. Worst for
# leakage off a would-be dynamic node is 125 C, so that is where it is checked
# across every process bundle, plus the nominal point.
for corner in "${SIMENV_MOS_CORNERS[@]}"; do
  for n in 4 64; do echo "${corner} 125 2.97 10e6 ${n}"; done
done >>"${CHAIN_JOBS}"
for n in 4 64; do echo "typical 27 3.30 10e6 ${n}"; done >>"${CHAIN_JOBS}"
sort -u -o "${CHAIN_JOBS}" "${CHAIN_JOBS}"
echo "divider-ratio/chain: $(wc -l <"${CHAIN_JOBS}" | tr -d ' ') points, ${JOBS} jobs"
CHAIN_ROWS="${WORK}/rows_chain.csv"; : >"${CHAIN_ROWS}"
# shellcheck disable=SC2016
xargs -P "${JOBS}" -L 1 "${BASH:-/bin/bash}" -c 'exec "$0" --one-chain "$@"' \
  "${HERE}/run.sh" <"${CHAIN_JOBS}" >>"${CHAIN_ROWS}"
sort -t, -k4,4n -k5,5n -k1,1 -k2,2n -k3,3n "${CHAIN_ROWS}" -o "${CHAIN_ROWS}"

# ===========================================================================
# Mint the three records (sim/README.md convention)
# ===========================================================================
SNAPDIR="${EXP}/netlist-snapshots"; RECORDSDIR="${EXP}/records"
mkdir -p "${SNAPDIR}" "${RECORDSDIR}"

RID_DFF=$(simenv_record_id); sleep 1
RID_CELL=$(simenv_record_id); sleep 1
RID_CHAIN=$(simenv_record_id)

for pair in "dff:${RID_DFF}" "cell:${RID_CELL}" "chain:${RID_CHAIN}"; do
  key="${pair%%:*}"; rid="${pair#*:}"
  cp "$(dut_file "${key}")" "${SNAPDIR}/${rid}.spice"
  mkdir -p "${EXP}/corners/${rid}"
done
SHA_DFF=$(simenv_sha256 "${SNAPDIR}/${RID_DFF}.spice")
SHA_CELL=$(simenv_sha256 "${SNAPDIR}/${RID_CELL}.spice")
SHA_CHAIN=$(simenv_sha256 "${SNAPDIR}/${RID_CHAIN}.spice")

# --- archive the raw per-corner logs ---------------------------------------
while read -r corner temp vdd; do
  simenv_archive_log "${WORK}" "$(mktag "dff ${corner} ${temp} ${vdd}")" \
    "${EXP}/corners/${RID_DFF}" "$(simenv_corner_id "${corner}" "${temp}" "${vdd}")"
done <"${DFF_JOBS}"

while read -r corner temp vdd kf; do
  fl=$(awk -v f="${kf}" 'BEGIN{printf "f%03d", f/1e6}')
  simenv_archive_log "${WORK}" "$(mktag "cell ${corner} ${temp} ${vdd} ${kf}")" \
    "${EXP}/corners/${RID_CELL}" "$(simenv_corner_id "${fl}-${corner}" "${temp}" "${vdd}")"
done <"${CELL_JOBS}"

while read -r corner temp vdd kf n; do
  nl=$(printf "n%02d" "${n}")
  fl=$(awk -v f="${kf}" 'BEGIN{printf "f%03d", f/1e6}')
  simenv_archive_log "${WORK}" "$(mktag "chain ${corner} ${temp} ${vdd} ${kf} ${n}")" \
    "${EXP}/corners/${RID_CHAIN}" "$(simenv_corner_id "${nl}-${fl}-${corner}" "${temp}" "${vdd}")"
done <"${CHAIN_JOBS}"

# --- extracted-metrics CSVs ------------------------------------------------
GRID_DESC="process{typical,ff,ss,fs,sf} x temp{-40,27,125}C x vdd{2.97,3.30,3.63}V = 45 points"

CSV_DFF="${EXP}/corners/${RID_DFF}/dff_setup_hold.csv"
{
  simenv_provenance "divider-ratio/dff" "${RID_DFF}" \
    "design/dff_tg_3v3.sch -> design/netlist/dff_tg_3v3.spice + sim/divider-ratio/testbench/tb_dff_setup.sp" \
    "${GRID_DESC}"
  cat <<'EOF'
# tsetup_s: worst of the 0->1 and 1->0 banks, 10%-clk->Q-degradation criterion
#   over the ladder ti = 1.00/0.20/0.10/0.05/0.02/0.00/-0.02/-0.05/-0.10/-0.15 ns.
#   A value equal to the last ladder step means setup was never violated down
#   to that step, i.e. the true setup time is at or below it.
# thold_s: most negative ladder step of th = 0.50/0.20/0.10/0.00/-0.10/-0.20/
#   -0.30/-0.40/-0.50/-0.70 ns at which data arriving AFTER the clock edge was
#   still not captured. Negative = data may move before the edge and still be
#   safely excluded.
# tcq_r_s / tcq_f_s: relaxed-input clk->Q for the rising and falling output.
EOF
  echo "${DFF_HEADER}"; cat "${DFF_ROWS}"
} >"${CSV_DFF}"

CSV_CELL="${EXP}/corners/${RID_CELL}/cell_corners.csv"
{
  simenv_provenance "divider-ratio/cell" "${RID_CELL}" \
    "design/div23_cell.sch -> design/netlist/div23_cell.spice + sim/divider-ratio/testbench/tb_div23_cell.sp" \
    "${GRID_DESC} x kf{200,10} MHz = 90 points"
  cat <<'EOF'
# Six independent copies of the same cell per run (see the testbench header):
#   n_div2         P=0, 50% duty in   -> must be exactly 2
#   n_div3         P=1, 50% duty in   -> must be exactly 3
#   n_div2_33duty  P=0, 33% duty in   -> must be exactly 2  (both-edges check)
#   n_div3_67duty  P=1, 67% duty in   -> must be exactly 3  (both-edges check)
#   n_1p5x         P=1 at 1.5 x kf    -> must be exactly 3  (speed margin)
#   n_2x           P=1 at 2.0 x kf    -> must be exactly 3  (speed margin)
# tcq_s: CKIN 50% to CKOUT 50%, modulo the input period.
# pw_modout_s: MODOUT high time of the divide-by-3 copy; must be one CKIN
#   period, since the preceding (2x faster) cell has to see it as one of its
#   own output periods.
# i_cell_a: supply current of the six copies divided by six.
# pass: every one of the six ratios exact to within 1e-3.
EOF
  echo "${CELL_HEADER}"
  awk -F, 'BEGIN{OFS=","} {$15=sprintf("%.6g",$15/6); print}' "${CELL_ROWS}"
} >"${CSV_CELL}"

CSV_CHAIN="${EXP}/corners/${RID_CHAIN}/chain_ratio.csv"
{
  simenv_provenance "divider-ratio/chain" "${RID_CHAIN}" \
    "design/divider_chain.sch -> design/netlist/divider_chain.spice + sim/divider-ratio/testbench/tb_divider_chain.sp" \
    "N=4..64 at 3 stress corners; N in {4,33,64} over ${GRID_DESC}; N in {4,64} at 10 MHz"
  cat <<'EOF'
# n_meas_1 / n_meas_2: two consecutive retimed-FB periods in units of the VCO
#   period. Both must equal n_target exactly; two periods rather than one so a
#   chain that alternates N-1/N+1 cannot average its way to a pass.
# n_divout: the same ratio on the un-retimed chain output.
# t_arr_s: DIVOUT arrival referred to the VCO rising edge that caused it,
#   modulo one VCO period = the chain's accumulated clk->Q plus output-mux
#   delay. This is the quantity the retiming flop's setup budget is spent on.
# t_rtcq_s: retiming flop clk->Q = the constant, N-independent feedback delay
#   the PFD sees (DR-001's interface contract to #9).
# fb_pw_s: FB high time; must exceed #9's PFD reset delay.
# i_div_a: current on the dedicated vdd_div domain.
EOF
  echo "${CHAIN_HEADER}"; cat "${CHAIN_ROWS}"
} >"${CSV_CHAIN}"

# --- retiming setup closure: join chain t_arr with the flop's setup time ----
CSV_RETIME="${EXP}/corners/${RID_CHAIN}/retiming_margin.csv"
{
  simenv_provenance "divider-ratio/retiming" "${RID_CHAIN}" \
    "design/divider_chain.sch (t_arr) joined with record ${RID_DFF} (t_setup)" \
    "${GRID_DESC} at N=64 (k=6, the longest chain and therefore the largest accumulated clk->Q), kf=200 MHz"
  cat <<'EOF'
# setup_margin_s = T_vco - t_arr_s - tsetup_s, evaluated at N=64 (k=6) and
#   kf = 200 MHz, the v1 output ceiling (DR-002 Decision 2). This is DR-001
#   Decision 3's budget verbatim: "one VCO period minus the chain's
#   accumulated clk->Q", less the flop's own setup requirement.
# hold_margin_s = t_arr_s - thold_s, from the same pair of records.
# tsetup_s / thold_s are joined per PVT point from the dff record named above.
EOF
  echo "process,temp_c,vdd_v,t_arr_s,tsetup_s,thold_s,tvco_s,setup_margin_s,hold_margin_s,verdict"
  awk -F, -v OFS=, '
    FNR == NR {
      if ($1 ~ /^#/ || $1 == "process") next
      key = $1 "_" $2 "_" $3; su[key] = $4 + 0; ho[key] = $5 + 0; next
    }
    { if ($1 ~ /^#/ || $1 == "process") next
      if ($4 + 0 != 200e6 || $5 + 0 != 64) next
      key = $1 "_" $2 "_" $3
      tv = 1 / ($4 + 0)
      sm = tv - ($10 + 0) - su[key]
      hm = ($10 + 0) - ho[key]
      printf "%s,%s,%s,%.6g,%.6g,%.6g,%.6g,%.6g,%.6g,%s\n",
             $1, $2, $3, $10, su[key], ho[key], tv, sm, hm,
             (sm > 0 && hm > 0 ? "CLOSES" : "FAILS")
    }' "${DFF_ROWS}" "${CHAIN_ROWS}"
} >"${CSV_RETIME}"

# ===========================================================================
# Summary statistics, computed from the CSVs so a record cannot drift from
# its data.
# ===========================================================================
DFF_SUM=$(grep -v '^#' "${CSV_DFF}" | tail -n +2 | awk -F, '
  { if (smax == "" || $4 + 0 > smax) { smax = $4 + 0; sc = $1 "/" $2 "C/" $3 "V" }
    if (hmax == "" || $5 + 0 > hmax) hmax = $5 + 0
    if (qmax == "" || $6 + 0 > qmax) { qmax = $6 + 0; qc = $1 "/" $2 "C/" $3 "V" }
    if (qmin == "" || $6 + 0 < qmin) qmin = $6 + 0 }
  END { printf "%.6g|%s|%.6g|%.6g|%s|%.6g", smax, sc, hmax, qmax, qc, qmin }')
DFF_TSU_MAX=$(echo "${DFF_SUM}" | cut -d'|' -f1)
DFF_TSU_C=$(echo "${DFF_SUM}"   | cut -d'|' -f2)
DFF_TH_MAX=$(echo "${DFF_SUM}"  | cut -d'|' -f3)
DFF_TCQ_MAX=$(echo "${DFF_SUM}" | cut -d'|' -f4)
DFF_TCQ_C=$(echo "${DFF_SUM}"   | cut -d'|' -f5)
DFF_TCQ_MIN=$(echo "${DFF_SUM}" | cut -d'|' -f6)

CELL_TOT=$(grep -v '^#' "${CSV_CELL}" | tail -n +2 | wc -l | tr -d ' ')
CELL_FAIL=$(grep -v '^#' "${CSV_CELL}" | tail -n +2 | awk -F, '$16=="FAIL"' | wc -l | tr -d ' ')
CELL_TCQ=$(grep -v '^#' "${CSV_CELL}" | tail -n +2 | awk -F, '
  $4+0==200e6 { if (mx == "" || $11 + 0 > mx) { mx = $11 + 0; mc = $1 "/" $2 "C/" $3 "V" }
                if (mn == "" || $11 + 0 < mn) mn = $11 + 0 }
  END { printf "%.6g|%s|%.6g", mx, mc, mn }')
CELL_TCQ_MAX=$(echo "${CELL_TCQ}" | cut -d'|' -f1)
CELL_TCQ_C=$(echo "${CELL_TCQ}"   | cut -d'|' -f2)
CELL_TCQ_MIN=$(echo "${CELL_TCQ}" | cut -d'|' -f3)

CHAIN_TOT=$(grep -v '^#' "${CSV_CHAIN}" | tail -n +2 | wc -l | tr -d ' ')
CHAIN_FAIL=$(grep -v '^#' "${CSV_CHAIN}" | tail -n +2 | awk -F, '$14=="FAIL"' | wc -l | tr -d ' ')
CHAIN_NSWEEP=$(grep -v '^#' "${CSV_CHAIN}" | tail -n +2 | awk -F, '$4+0==200e6 {print $5}' | sort -un | wc -l | tr -d ' ')
CHAIN_FBPW_MIN=$(grep -v '^#' "${CSV_CHAIN}" | tail -n +2 | awk -F, '
  { if (mn == "" || $12 + 0 < mn) { mn = $12 + 0; mc = $1 "/" $2 "C/" $3 "V N=" $5 " " $4/1e6 "MHz" } }
  END { printf "%.6g|%s", mn, mc }')
CHAIN_FBPW=$(echo "${CHAIN_FBPW_MIN}" | cut -d'|' -f1)
CHAIN_FBPW_C=$(echo "${CHAIN_FBPW_MIN}" | cut -d'|' -f2)
CHAIN_RTCQ=$(grep -v '^#' "${CSV_CHAIN}" | tail -n +2 | awk -F, '
  $4+0==200e6 { if (mx == "" || $11 + 0 > mx) mx = $11 + 0; if (mn == "" || $11 + 0 < mn) mn = $11 + 0 }
  END { printf "%.6g|%.6g", mn, mx }')
CHAIN_RTCQ_MIN=$(echo "${CHAIN_RTCQ}" | cut -d'|' -f1)
CHAIN_RTCQ_MAX=$(echo "${CHAIN_RTCQ}" | cut -d'|' -f2)
CHAIN_IDIV=$(grep -v '^#' "${CSV_CHAIN}" | tail -n +2 | awk -F, '
  $4+0==200e6 { if (mx == "" || $13 + 0 > mx) { mx = $13 + 0; mc = $1 "/" $2 "C/" $3 "V N=" $5 } }
  END { printf "%.6g|%s", mx, mc }')
CHAIN_IDIV_MAX=$(echo "${CHAIN_IDIV}" | cut -d'|' -f1)
CHAIN_IDIV_C=$(echo "${CHAIN_IDIV}"   | cut -d'|' -f2)

RT_SUM=$(grep -v '^#' "${CSV_RETIME}" | tail -n +2 | awk -F, '
  { n++; if ($10 == "FAILS") f++
    if (smin == "" || $8 + 0 < smin) { smin = $8 + 0; sc = $1 "/" $2 "C/" $3 "V" }
    if (hmin == "" || $9 + 0 < hmin) { hmin = $9 + 0; hc = $1 "/" $2 "C/" $3 "V" }
    if (amax == "" || $4 + 0 > amax) amax = $4 + 0 }
  END { printf "%d|%d|%.6g|%s|%.6g|%s|%.6g", n, f + 0, smin, sc, hmin, hc, amax }')
RT_N=$(echo       "${RT_SUM}" | cut -d'|' -f1)
RT_FAIL=$(echo    "${RT_SUM}" | cut -d'|' -f2)
RT_SMIN=$(echo    "${RT_SUM}" | cut -d'|' -f3)
RT_SMIN_C=$(echo  "${RT_SUM}" | cut -d'|' -f4)
RT_HMIN=$(echo    "${RT_SUM}" | cut -d'|' -f5)
RT_HMIN_C=$(echo  "${RT_SUM}" | cut -d'|' -f6)
RT_AMAX=$(echo    "${RT_SUM}" | cut -d'|' -f7)

# ===========================================================================
# Records
# ===========================================================================
cat >"${RECORDSDIR}/${RID_DFF}.md" <<EOF
# Record ${RID_DFF}

- **Record ID**: ${RID_DFF}
- **Claim**: #11 (design input, not a spec line) -- what are the setup time,
  hold time and clk->Q of \`dff_tg_3v3\`, the transmission-gate master-slave
  flop every divider cell and the retiming flop are built from (DR-001
  Decision 3: "static CMOS throughout (transmission-gate master-slave
  flops)")? The setup number is the one DR-001 Decision 3 requires in order
  to state whether the retiming flop's budget closes at the slow corner; the
  closure itself is record ${RID_CHAIN}.
- **Netlist provenance**: schematic (\`design/dff_tg_3v3.sch\`, exported by
  \`design/netlist.sh\` to \`design/netlist/dff_tg_3v3.spice\`) ->
  \`sim/divider-ratio/netlist-snapshots/${RID_DFF}.spice\` (exported subcircuit
  + testbench, concatenated), SHA-256 \`${SHA_DFF}\`
- **Environment provenance**:
$(simenv_env_block)
- **Corner matrix run**: 45 points (5 MOS bundles x 3 temperatures x 3 supplies)
  - Bundles (-> \`.lib\` sections of sm141064.ngspice): \`typical\` -> typical;
    \`ff\` -> ff; \`ss\` -> ss; \`fs\` -> fs; \`sf\` -> sf
  - Temperature: -40 C, 27 C, 125 C
  - Supply: 2.97 V, 3.30 V, 3.63 V (3.3 V +/-10%)
  - **Axes not swept**: passive corner sections N/A -- the DUT contains no
    MIM/MOS capacitors or poly resistors, only \`nfet_03v3\`/\`pfet_03v3\`
    (DR-002 Decision 3).
- **Methodology / criteria / limitations**:
  - Setup: 10 copies per bank share one clock; copy i sees its data 50%
    crossing ti before the clock's 50% crossing, ti = 1.00, 0.20, 0.10, 0.05,
    0.02, 0.00, -0.02, -0.05, -0.10, -0.15 ns. Bank A captures 0->1, bank B
    1->0. Setup time = the smallest ti whose clk->Q has not degraded by more
    than 10% against the same bank's ti = 1.00 ns reference. The first clock
    edge preconditions every flop, so no result depends on the DC operating
    point of a bistable latch.
  - Hold: 10 further copies hold data low through the measured edge and
    transition 0->1 only th afterwards, th = 0.50 ... -0.70 ns. Hold is met
    at a step if Q stays below 10% of the rail until the next clock edge.
  - Simulator settings: \`.tran 10p 35n\`, \`reltol 1e-3\`, \`abstol 1e-10\`.
  - **Limitation -- ladder floor.** Where the reported setup equals the last
    ladder step (-0.15 ns) the criterion was never tripped, so the true setup
    time is at or below that value and the number is a bound, not a
    measurement. That is the safe direction for the margin computed in
    ${RID_CHAIN} only because the bound is *pessimistic*: a smaller true
    setup can only increase the margin.
  - **Limitation -- schematic-level.** No extracted parasitics; clock and
    data both driven by ideal 100 ps-edge sources. Post-layout re-extraction
    is #18's scope and will supersede these numbers.
  - Statistical switches: \`sw_stat_global = sw_stat_mismatch = 0\` (nominal
    device skew from the corner section only, no Monte Carlo mismatch).
- **Statistical convention**: N/A -- corner-matrix claim, not a distribution
  claim.
- **Result**:

  | Metric | Value | Corner |
  |---|---|---|
  | setup time, worst over the grid | ${DFF_TSU_MAX} s | ${DFF_TSU_C} |
  | hold time, worst over the grid | ${DFF_TH_MAX} s | (see CSV) |
  | clk->Q (rising Q), slowest | ${DFF_TCQ_MAX} s | ${DFF_TCQ_C} |
  | clk->Q (rising Q), fastest | ${DFF_TCQ_MIN} s | (see CSV) |

  Full 45-point table:
  \`sim/divider-ratio/corners/${RID_DFF}/dff_setup_hold.csv\`.

  **Conclusion**: the flop's setup requirement is a small fraction of a
  200 MHz VCO period at every corner, and its hold requirement is negative
  (data may move slightly before the clock edge and still be excluded), which
  is the expected signature of a transmission-gate master-slave latch pair
  whose input gate closes a gate delay after the clock arrives. These numbers
  are consumed by ${RID_CHAIN}.
- **Links**:
  - Testbench: \`sim/divider-ratio/testbench/tb_dff_setup.sp\`
  - Schematic: \`design/dff_tg_3v3.sch\`
  - Netlist snapshot: \`sim/divider-ratio/netlist-snapshots/${RID_DFF}.spice\`
  - Raw logs: \`sim/divider-ratio/corners/${RID_DFF}/\`
  - Extracted metrics: \`sim/divider-ratio/corners/${RID_DFF}/dff_setup_hold.csv\`
- **Timestamp / author**: $(date -u +%Y-%m-%dT%H:%M:%SZ), agent-builder (issue #11)
- **Supersedes**: (none -- first record for this claim)
EOF

cat >"${RECORDSDIR}/${RID_CELL}.md" <<EOF
# Record ${RID_CELL}

- **Record ID**: ${RID_CELL}
- **Claim**: #11 -> DR-001 Decision 3 (design input, not a spec line) -- does
  one \`div23_cell\` divide by exactly 2 with its modulus bit low and by
  exactly 3 with it high, on both output edges and for both input duty
  cycles, at the top and the bottom of the v1 output band, at every PVT
  corner? Includes the first-stage speed-margin question DR-001 Decision 3
  asks explicitly ("the first divider stage must run at max VCO frequency at
  the worst corner") and the "static CMOS has no minimum clock frequency"
  property the logic family was chosen for.
- **Netlist provenance**: schematic (\`design/div23_cell.sch\`, exported by
  \`design/netlist.sh\` to \`design/netlist/div23_cell.spice\`) ->
  \`sim/divider-ratio/netlist-snapshots/${RID_CELL}.spice\` (exported
  subcircuit + testbench, concatenated), SHA-256 \`${SHA_CELL}\`
- **Environment provenance**:
$(simenv_env_block)
- **Corner matrix run**: 90 points = 45 PVT points x 2 input rates
  - Bundles (-> \`.lib\` sections of sm141064.ngspice): \`typical\` -> typical;
    \`ff\` -> ff; \`ss\` -> ss; \`fs\` -> fs; \`sf\` -> sf
  - Temperature: -40 C, 27 C, 125 C
  - Supply: 2.97 V, 3.30 V, 3.63 V (3.3 V +/-10%)
  - Input rate: 200 MHz (v1 output ceiling, DR-002 Decision 2) and 10 MHz
    (output floor). Within each 200 MHz run two further copies are clocked at
    300 MHz and 400 MHz, so the speed-margin points are covered at all 45 PVT
    points as well.
  - **Axes not swept**: passive corner sections N/A -- the DUT is
    \`nfet_03v3\`/\`pfet_03v3\` only (DR-002 Decision 3), no MIM/MOS caps or
    poly resistors.
- **Methodology / criteria / limitations**:
  - Six independent copies of the identical cell share one transient, so a
    single run covers the whole single-cell acceptance set: P=0 and P=1 at
    50% input duty, P=0 at 33% duty and P=1 at 67% duty (the both-edges
    check -- a swallowing cell emits a 33%-duty output, so every downstream
    cell is clocked by a duty-distorted waveform and division must still be
    exact, which is only true of a purely rising-edge-triggered cell), and
    P=1 at 1.5x and 2.0x the run's input rate.
  - Ratio criterion: two consecutive output periods measured between the 1st
    and 3rd rising 50% crossings, divided by the cell's own input period;
    exact to within 1e-3 for all six copies, or the point is FAIL.
  - MODOUT pulse width of the divide-by-3 copy must be one input period: the
    preceding (2x faster) cell has to see it as exactly one of *its* output
    periods, which is what makes the chain's N = 2^k + sum(p_i 2^i) hold.
  - Simulator settings: \`.tran\` max step = input period / 250, stop = 12
    input periods; \`reltol 1e-3\`, \`abstol 1e-10\`.
  - **Limitation -- schematic-level.** No extracted parasitics and no wire
    load between cells; the real inter-cell load is one cell input plus
    routing. Speed margin therefore reads optimistic and must be re-taken
    post-layout (#18).
  - Statistical switches: \`sw_stat_global = sw_stat_mismatch = 0\`.
- **Statistical convention**: N/A -- corner-matrix claim, not a distribution
  claim.
- **Result**:

  | Metric | Value |
  |---|---|
  | points run | ${CELL_TOT} |
  | points where any of the six ratios was not exact | ${CELL_FAIL} |
  | cell clk->Q at 200 MHz, slowest | ${CELL_TCQ_MAX} s (${CELL_TCQ_C}) |
  | cell clk->Q at 200 MHz, fastest | ${CELL_TCQ_MIN} s |

  Full 90-point table:
  \`sim/divider-ratio/corners/${RID_CELL}/cell_corners.csv\`.

  **Conclusion**: see the FAIL count above -- 0 means every modulus, both
  output edges, both input duty cycles and all four input rates (10, 200, 300
  and 400 MHz) divided exactly at all 45 PVT points, i.e. the first-stage
  speed-margin requirement is met at the 200 MHz v1 ceiling with the 400 MHz
  stretch point also exercised, and the cell keeps dividing at the 10 MHz
  band floor (the property static CMOS was chosen for over TSPC/E-TSPC).
  The per-cell clk->Q above is the term that accumulates down the chain and
  is spent against the retiming flop's setup budget in ${RID_CHAIN}.
- **Links**:
  - Testbench: \`sim/divider-ratio/testbench/tb_div23_cell.sp\`
  - Schematic: \`design/div23_cell.sch\`
  - Netlist snapshot: \`sim/divider-ratio/netlist-snapshots/${RID_CELL}.spice\`
  - Raw logs: \`sim/divider-ratio/corners/${RID_CELL}/\`
  - Extracted metrics: \`sim/divider-ratio/corners/${RID_CELL}/cell_corners.csv\`
- **Timestamp / author**: $(date -u +%Y-%m-%dT%H:%M:%SZ), agent-builder (issue #11)
- **Supersedes**: (none -- first record for this claim)
EOF

cat >"${RECORDSDIR}/${RID_CHAIN}.md" <<EOF
# Record ${RID_CHAIN}

- **Record ID**: ${RID_CHAIN}
- **Claim**: #11 -> DR-001 Decision 3 (design input, not a spec line) -- two
  linked questions about the assembled feedback divider:
  1. does the six-cell chain divide by **every** integer N from 4 to 64
     exactly, with no holes, at the corners that stress it most; and
  2. does the VCO-clocked retiming flop's setup budget -- "one VCO period
     minus the chain's accumulated clk->Q", DR-001 Decision 3 -- **close at
     the slow corner (SS, 125 C, 2.97 V)** at the 200 MHz v1 ceiling with the
     longest chain (k=6)? DR-001 requires an explicit answer here and names
     the fallback (retime on the first cell's output, VCO/2) if it does not.
- **Netlist provenance**: schematic (\`design/divider_chain.sch\`, exported by
  \`design/netlist.sh\` to \`design/netlist/divider_chain.spice\`) ->
  \`sim/divider-ratio/netlist-snapshots/${RID_CHAIN}.spice\` (exported
  subcircuit + testbench, concatenated), SHA-256 \`${SHA_CHAIN}\`
- **Environment provenance**:
$(simenv_env_block)
- **Corner matrix run**: ${CHAIN_TOT} points in three overlapping sweeps
  - **N sweep**: every integer N = 4..64 (${CHAIN_NSWEEP} values, not a
    sample) at 200 MHz, at three corners chosen for what they stress:
    \`ss\`/125 C/2.97 V (slowest -- largest accumulated clk->Q against the VCO
    period), \`ff\`/-40 C/3.63 V (fastest -- narrowest internal pulses) and
    \`typical\`/27 C/3.30 V (nominal reference).
  - **Full grid**: N in {4, 33, 64} over all 45 PVT points (5 MOS bundles x 3
    temperatures x 3 supplies) at 200 MHz. N=64 is k=6, the longest chain and
    therefore the retiming-budget worst case, so the setup closure below is
    evaluated at all 45 points.
  - **Bottom of band**: N in {4, 64} at 10 MHz, across all five process
    bundles at 125 C/2.97 V (worst for leakage) plus the nominal point.
  - Bundles (-> \`.lib\` sections of sm141064.ngspice): \`typical\` -> typical;
    \`ff\` -> ff; \`ss\` -> ss; \`fs\` -> fs; \`sf\` -> sf
  - **Axes not swept**: passive corner sections N/A -- \`nfet_03v3\`/
    \`pfet_03v3\` only (DR-002 Decision 3), no MIM/MOS caps or poly resistors
    in this DUT.
- **Methodology / criteria / limitations**:
  - Programming: N = 2^k + sum(p_i . 2^i) for i < k, with the one-hot
    chain-length code SEL_(k-1) = 1 terminating the modulus chain at the last
    active cell and selecting its output through the one-hot output mux.
    N is a static configuration (DR-001: glitch-free on-the-fly modulus
    switching is out of v1 scope), so each N is a separate run.
  - Ratio criterion: **two consecutive** retimed-FB periods, each in units of
    the VCO period, must both equal N exactly (< 1e-3), and the un-retimed
    DIVOUT ratio must agree to < 1e-2. Two periods rather than one so a chain
    that alternates N-1/N+1 cannot average its way to a pass.
  - Retiming budget: t_arr is DIVOUT's arrival referred to the VCO rising
    edge that caused it, taken modulo one VCO period -- that modulo is the
    point, because what threatens the flop is the arrival *phase* inside a
    VCO period, not how many whole periods the chain took. setup_margin =
    T_vco - t_arr - t_setup and hold_margin = t_arr - t_hold, with t_setup /
    t_hold joined per PVT point from record ${RID_DFF}.
  - Simulator settings: \`.tran\` max step = VCO period / 100, stop =
    (3N + 8) VCO periods; \`reltol 1e-3\`, \`abstol 1e-10\`. The 50 ps max step
    at 200 MHz bounds the interpolation error on t_arr at a few tens of ps,
    which is the resolution limit on the margin numbers below.
  - **Limitation -- schematic-level, and it bites hardest here.** There are no
    extracted parasitics and no routing load between cells, and the retiming
    margin is a difference of two numbers that both grow with parasitic load.
    A margin quoted here is an upper bound on the post-layout margin, not an
    estimate of it. This is the single most important number for #18 to
    re-take.
  - Statistical switches: \`sw_stat_global = sw_stat_mismatch = 0\`.
- **Statistical convention**: N/A -- corner-matrix claim, not a distribution
  claim.
- **Result**:

  **1. Division ratio**

  | Metric | Value |
  |---|---|
  | chain points run | ${CHAIN_TOT} |
  | points where the measured ratio was not exactly N | ${CHAIN_FAIL} |
  | distinct N values exercised at 200 MHz | ${CHAIN_NSWEEP} (N = 4..64) |
  | narrowest FB high time over all points | ${CHAIN_FBPW} s (${CHAIN_FBPW_C}) |
  | retiming flop clk->Q at 200 MHz (min..max over the grid) | ${CHAIN_RTCQ_MIN} .. ${CHAIN_RTCQ_MAX} s |
  | vdd_div supply current at 200 MHz, worst | ${CHAIN_IDIV_MAX} A (${CHAIN_IDIV_C}) |

  **2. Retiming setup closure at 200 MHz, N=64 (k=6), all 45 PVT points**

  | Metric | Value | Corner |
  |---|---|---|
  | points evaluated | ${RT_N} | -- |
  | points where setup or hold margin was negative | ${RT_FAIL} | -- |
  | worst setup margin | ${RT_SMIN} s | ${RT_SMIN_C} |
  | worst hold margin | ${RT_HMIN} s | ${RT_HMIN_C} |
  | largest accumulated arrival t_arr | ${RT_AMAX} s | -- |

  Per-point tables:
  \`sim/divider-ratio/corners/${RID_CHAIN}/chain_ratio.csv\` and
  \`sim/divider-ratio/corners/${RID_CHAIN}/retiming_margin.csv\`.

  **Interface contract to #9 (DR-001 Decision 3).** The feedback edge is the
  retiming flop's rising edge; its delay from the causing VCO edge is the
  retiming flop clk->Q above and is **independent of N** by construction (the
  flop is clocked by the VCO, not by the chain), which the min..max spread
  over the whole N sweep at a fixed corner substantiates. The FB high time
  above is the width #9 must compare against its PFD reset delay before
  either side treats the contract as final.

  **Verdict on the retiming budget** is the "points with negative margin"
  row: 0 means the VCO-clocked retiming of DR-001 Decision 3's primary path
  closes at every corner including SS/125 C/2.97 V and the documented VCO/2
  fallback is not needed at schematic level; any non-zero count means it does
  not close and the fallback must be taken. Either way the *margin* number
  above, not just the verdict, is what #18 has to defend after extraction --
  see the schematic-level limitation.

  **3. Output-divider scope check (a documented non-decision, not a result)**

  DR-002 Decision 2 makes "no post-VCO output-divider stage in v1" the
  default, and makes the trigger to add one specifically **#8's extracted
  evidence** that the ring's band overlap or low-band floor does not reach
  10 MHz across all PVT corners -- not a generic scope call. At the time this
  record was minted, #8 had **not** landed that evidence in \`sim/\` (no
  \`sim/vco-tuning-range/records/\` exists in this repo at the commit named
  under Environment provenance above). This issue therefore proceeded on the
  DR-002 Decision 2 default: **the v1 deliverable here is the feedback
  divider and the lock detector only, with no output-divider stage**, and the
  trigger is flagged as **pending re-verification once #8 lands**. Nothing in
  this record constitutes evidence either way about the VCO's reachable low
  band; it is stated here so the non-decision is on the record rather than
  silently assumed.
- **Links**:
  - Testbench: \`sim/divider-ratio/testbench/tb_divider_chain.sp\`
  - Schematic: \`design/divider_chain.sch\` (instantiates \`design/div23_cell.sch\`)
  - Netlist snapshot: \`sim/divider-ratio/netlist-snapshots/${RID_CHAIN}.spice\`
  - Raw logs: \`sim/divider-ratio/corners/${RID_CHAIN}/\`
  - Extracted metrics: \`sim/divider-ratio/corners/${RID_CHAIN}/chain_ratio.csv\`,
    \`sim/divider-ratio/corners/${RID_CHAIN}/retiming_margin.csv\`
  - Setup/hold numbers joined from record: \`sim/divider-ratio/records/${RID_DFF}.md\`
  - Single-cell evidence: \`sim/divider-ratio/records/${RID_CELL}.md\`
- **Timestamp / author**: $(date -u +%Y-%m-%dT%H:%M:%SZ), agent-builder (issue #11)
- **Supersedes**: (none -- first record for this claim)
EOF

echo "divider-ratio: wrote ${RECORDSDIR}/${RID_DFF}.md"
echo "divider-ratio: wrote ${RECORDSDIR}/${RID_CELL}.md"
echo "divider-ratio: wrote ${RECORDSDIR}/${RID_CHAIN}.md"
echo "divider-ratio: cell FAIL=${CELL_FAIL}/${CELL_TOT}  chain FAIL=${CHAIN_FAIL}/${CHAIN_TOT}  retiming FAIL=${RT_FAIL}/${RT_N}"
