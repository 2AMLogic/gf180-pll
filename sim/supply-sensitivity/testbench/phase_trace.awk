# gf180-pll :: supply-sensitivity :: per-REF-cycle REF->FB phase trace (#395)
#
# Extracted out of run.sh's --one-dyn so it can be unit-tested against a
# synthetic trace without a multi-hour ngspice run (sim/tests/, or the
# equivalent under this experiment's testbench/) -- see the block comment in
# run.sh's --one-dyn ("--- per-REF-cycle phase trace") for what this measures
# and why.  Behaviour is unchanged from the inline version it replaces; this
# file IS what --one-dyn invokes, not a copy of it.
#
# Input: `supply_transient_full.csv`, ngspice's own `wrdata ... v(vctrl)
# v(lock) v(vdd) v(fb) v(ref)` -- one (time, value) COLUMN PAIR per vector, so
# fields are $1/$2 vctrl, $3/$4 lock, $5/$6 vdd, $7/$8 fb, $9/$10 ref.
#
# Parameters (both -v, both required):
#   vth   the rising-edge threshold, in volts -- v_lo/2, the SAME threshold
#         tb_supply_dyn.sp's own .meas phi01..phi12 use, on both REF and FB.
#   halfT half a reference period, in seconds -- a REF/FB pair further apart
#         than this is dropped rather than folded (the aliasing guard).
#
# Output columns: t_ref_s,phi_ns,lock_v,vctrl_v,vdd_v
#   t_ref_s  the interpolated v(ref) rising crossing, one row per reference
#            cycle whose paired FB edge survives the halfT guard
#   phi_ns   (nearest v(fb) rising crossing) - t_ref_s, in ns; positive means
#            FB LAGS REF
#   lock_v / vctrl_v / vdd_v
#            the ngspice sample nearest the REF crossing, un-interpolated
/^[ \t]*[-0-9]/ {
  tf = $7 + 0; vf = $8 + 0; tr = $9 + 0; vr = $10 + 0;
  if (have) {
    if (pvr < vth && vr >= vth) {
      RT[++nr] = ptr + (tr - ptr) * (vth - pvr) / (vr - pvr);
      RL[nr] = $4 + 0; RC[nr] = $2 + 0; RD[nr] = $6 + 0;
    }
    if (pvf < vth && vf >= vth)
      FT[++nf] = ptf + (tf - ptf) * (vth - pvf) / (vf - pvf);
  }
  ptr = tr; pvr = vr; ptf = tf; pvf = vf; have = 1;
}
END {
  if (nf < 1) exit 0;
  j = 1;
  for (i = 1; i <= nr; i++) {
    while (j < nf && \
           (FT[j+1] - RT[i]) * (FT[j+1] - RT[i]) < \
           (FT[j]   - RT[i]) * (FT[j]   - RT[i])) j++;
    d = FT[j] - RT[i];
    if (d > -halfT && d < halfT)
      printf "%.12g,%.6f,%.6g,%.6g,%.6g\n", RT[i], d * 1e9, RL[i], RC[i], RD[i];
  }
}
