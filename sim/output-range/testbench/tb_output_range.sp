* gf180-pll :: output-range :: closed-loop output-band coverage testbench (#12)
*
* DUT: the SAME full closed loop as sim/lock-time (VCO #8, PFD/CP #9, loop
* filter #10, feedback divider #11), assembled by
* sim/lib/assemble_closed_loop.sh into "dut.spice" and included below.  This
* bench answers a different question than lock-time: not "how long does the
* loop take to lock", but "does the loop reach the ratified output-band EDGE
* frequencies at all, and with how much control-voltage headroom to the
* usable 0.9-2.7 V window" -- complementing (not re-deriving) #8's open-loop
* vco-tuning-range characterization, which is what this bench's initial
* condition and target selection are taken from (see run.sh).
*
* Same net names and topology as tb_lock_time.sp; see that file's header for
* the full description.
*
* Expects from the generated header (sim/lib/simenv.sh): the same param set
* as tb_lock_time.sp (vsup, fref, bnd*v, icp*v, iunit, sel*v/p*v, vctrl_ic,
* t_force, tstep, tstop, lockthresh). vctrl_ic here is NOT cold-start-vs-
* re-lock -- it is run.sh's best open-loop estimate of the locked Vctrl (from
* sim/vco-tuning-range's own measured f(Vctrl) table), used ONLY to keep the
* required simulated transient short enough to be tractable (see this
* record's Methodology field): the loop still closes and settles on its own,
* this just avoids re-proving cold-start slewing, which is lock-time's (#12)
* job, not this bench's.
*
* Expects "dut.spice" (sim/lib/assemble_closed_loop.sh's output) to have been
* copied into the run directory by testbench/run.sh.

.include "dut.spice"

*------------------------------------------------------------------ supplies
vdd    vdd    0 dc 'vsup'
vss    vss    0 dc 0
vddvco vddvco 0 dc 'vsup'
vddiv  vddiv  0 dc 'vsup'

*----------------------------------------------------------- reference clock
vref ref 0 pulse(0 'vsup' 20n 200p 200p '0.5/fref-200p' '1/fref')

*----------------------------------------------------- static configuration
vbnd0 bnd0 0 dc 'bnd0v'
vbnd1 bnd1 0 dc 'bnd1v'
vbnd2 bnd2 0 dc 'bnd2v'
vicp0 icp0 0 dc 'icp0v'
vicp1 icp1 0 dc 'icp1v'
vsel0 sel0 0 dc 'sel0v'
vsel1 sel1 0 dc 'sel1v'
vsel2 sel2 0 dc 'sel2v'
vsel3 sel3 0 dc 'sel3v'
vsel4 sel4 0 dc 'sel4v'
vsel5 sel5 0 dc 'sel5v'
vp0   pb0  0 dc 'p0v'
vp1   pb1  0 dc 'p1v'
vp2   pb2  0 dc 'p2v'
vp3   pb3  0 dc 'p3v'
vp4   pb4  0 dc 'p4v'
vp5   pb5  0 dc 'p5v'

iibn vdd ibn dc 'iunit'
iicn vdd icn dc 'iunit'
iibp ibp 0 dc 'iunit'
iicp icp 0 dc 'iunit'

*--------------------------------------------------------------------- DUT
xpfdcp ref fb icp0 icp1 ibn icn ibp icp vctrl up dn vdd vss pfd_cp
xlf    vctrl vss loop_filter
xvco   vctrl bnd0 bnd1 bnd2 clk vddvco vss vco
xdiv   clk pb0 pb1 pb2 pb3 pb4 pb5 sel0 sel1 sel2 sel3 sel4 sel5 divout fb vddiv vss divider_chain
xlock  up dn lock vwin vdd vss lock_detector

.ic v(xvco.Y1)=0 v(xvco.Y2)='vsup' v(xvco.Y3)=0 v(xvco.Y4)='vsup' v(xvco.Y5)=0

* Released clamp seeding VCTRL near run.sh's open-loop estimate of the
* locked value (see header comment above and this record's Methodology) --
* same mechanism as tb_lock_time.sp.
vsetv vsetnode 0 dc 'vctrl_ic'
vsctrl sctrl 0 pulse('vsup' 0 't_force' 100p 100p '2*tstop' '4*tstop')
sforce vctrl vsetnode sctrl 0 SWFORCE
.model SWFORCE SW(Ron=10 Roff=1G Vt='vsup/2' Vh=0)

.options reltol=1e-3 abstol=1e-9 vntol=1e-4 chgtol=1e-13
* The 4th .tran argument (tmax) is LOAD-BEARING -- see tb_lock_time.sp's
* identical note and sim/lib/simenv.sh's SIMENV_CLOSED_LOOP_TMAX. This bench
* was the worse of the two violators before #65: with the ceiling defaulting
* to the print step {tstep} = 1/(50*f_out), the 10 MHz `lo` edge ran at a 2 ns
* internal ceiling, and 91% of its measured internal steps were LONGER than
* the PFD's entire 0.33-0.39 ns set pulse.
.tran {tstep} {tstop} 0 {tmax}

*------------------------------------------------------------- measurements
* Same real lock_detector criterion as tb_lock_time.sp -- this bench also
* reports whether the loop actually LOCKED at the target frequency, not just
* that Vctrl landed somewhere plausible.
.measure tran t_lock_last_rise when v(lock)='lockthresh' rise=last
.measure tran lock_at_end find v(lock) at='tstop-1p'
* The control-voltage margin measurement this campaign exists for.
.measure tran vctrl_final find v(vctrl) at='tstop-1p'

* Optional full-transient waveform capture -- see tb_lock_time.sp's header
* comment above the identical `.control` block for the rationale (#49's
* Vctrl-anomaly prerequisite; no extra analysis cost, left on unconditionally).
.control
run
wrdata waveform.csv v(vctrl) v(up) v(dn) v(lock) v(vwin)
.endc
.end
