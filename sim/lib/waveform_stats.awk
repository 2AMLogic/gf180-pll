# gf180-pll :: closed-loop waveform statistics (#65)
#
# Reads one `waveform.csv` as written by tb_lock_time.sp / tb_output_range.sp's
# `.control` block:
#
#   wrdata waveform.csv v(vctrl) v(up) v(dn) v(lock) v(vwin)
#
# ngspice's `wrdata` emits an independent (time, value) COLUMN PAIR per vector,
# so the layout is:
#
#   c1=t  c2=vctrl | c3=t  c4=up | c5=t  c6=dn | c7=t  c8=lock | c9=t  c10=vwin
#
# and -- load-bearing for everything below -- for a transient those rows are the
# integrator's ACCEPTED INTERNAL TIMEPOINTS, not the `.tran` print grid. That is
# what makes a committed waveform CSV an auditable record of the internal step
# sequence, and it is why `sim/lock-time/records/20260801-101734-5eb00db.md`
# could measure the internal-timestep-bound violation from already-committed
# artifacts without re-simulating anything.
#
# This script exists so those numbers are re-derivable by anyone reading a
# record, rather than recomputed ad hoc per session. It reproduces that
# record's published figures for its own three artifacts (verified: mean
# internal step 0.230 ns / 0.232 ns / 1.756 ns, `up` duty 86.7%, vctrl_final
# 3.13821 V).
#
# Usage:
#   awk -v vsup=3.30 -f sim/lib/waveform_stats.awk <waveform.csv>
#
# Optional -v knobs:
#   vsup      supply, volts (default 3.30) -- digital threshold is vsup/2
#   setpulse  PFD internal set-pulse width, seconds (default 0.33e-9; see
#             sim/README.md "Closed-loop internal-timestep bound")
#   label     free-form tag echoed in the output
#
# Output is `key value` lines (one per line, stable order) so a record can cite
# individual numbers without re-parsing a table.

BEGIN {
  if (vsup == 0)     vsup = 3.30
  if (setpulse == 0) setpulse = 0.33e-9
  vth = vsup / 2
  n = 0
  # Time-weighted high-duration accumulators for the two PFD outputs.
  up_hi = 0; dn_hi = 0
  step_sum = 0; step_max = 0; step_min = 1e30; over = 0
}

# wrdata pads with trailing whitespace; skip anything that is not a data row.
NF < 10 { next }

{
  t = $1 + 0
  vctrl = $2 + 0
  up = $4 + 0
  dn = $6 + 0
  lock = $8 + 0

  if (n > 0) {
    dt = t - t_prev
    if (dt > 0) {
      step_sum += dt
      if (dt > step_max) step_max = dt
      if (dt < step_min) step_min = dt
      if (dt > setpulse) over++
      nstep++
      # Left-endpoint (previous sample's) level over the interval it spans --
      # the convention the prior record's duty figures used.
      if (up_prev > vth)   up_hi += dt
      if (dn_prev > vth)   dn_hi += dt
      if (lock_prev > vth) lock_hi += dt
    }
  } else {
    t_first = t
  }

  t_prev = t; up_prev = up; dn_prev = dn; lock_prev = lock
  vctrl_last = vctrl; t_last = t
  n++
}

END {
  if (nstep < 1) { print "error no_data_rows"; exit 1 }
  span = t_last - t_first
  if (label != "") print "label", label
  print "rows", n
  print "t_start_s", sprintf("%.6g", t_first)
  print "t_end_s", sprintf("%.6g", t_last)
  print "window_s", sprintf("%.6g", span)
  print "internal_steps", nstep
  print "step_mean_s", sprintf("%.6g", step_sum / nstep)
  print "step_max_s", sprintf("%.6g", step_max)
  print "step_min_s", sprintf("%.6g", step_min)
  print "step_mean_over_max", sprintf("%.4g", (step_sum / nstep) / step_max)
  print "set_pulse_s", sprintf("%.6g", setpulse)
  print "steps_over_set_pulse", over
  print "steps_over_set_pulse_frac", sprintf("%.4g", over / nstep)
  print "steps_per_set_pulse", sprintf("%.4g", setpulse / (step_sum / nstep))
  print "vth_v", sprintf("%.4g", vth)
  print "up_duty", sprintf("%.4g", up_hi / span)
  print "dn_duty", sprintf("%.4g", dn_hi / span)
  print "lock_duty", sprintf("%.4g", lock_hi / span)
  print "vctrl_final_v", sprintf("%.6g", vctrl_last)
}
