* gf180-pll :: lock-time :: closed-loop lock-acquisition testbench (#12)
*
* DUT: the FULL closed loop -- design/vco.sch (#8), pfd_cp (#9), loop_filter
* (#10), divider_chain (#11), per DR-001's Type-II charge-pump architecture --
* assembled by sim/lib/assemble_closed_loop.sh into "dut.spice" and included
* below.  Nothing in this deck re-implements any block behaviourally: every
* device is the real, corner-swept transistor-level netlist the other four
* issues already characterized.
*
* Topology (net names used below):
*   ref   -- external reference clock, frequency 'fref'
*   fb    -- divider's retimed feedback edge, back into the PFD
*   vctrl -- the ONE control node: PFD/CP's VOUT = loop filter's VCTRL pin =
*            VCO's VCTRL pin (the filter is a pure shunt network to ground,
*            per design/README.md's block diagram -- there is no separate
*            "into"/"out of the filter" node)
*   clk   -- VCO output, feeds the divider's VCO clock input
*   up/dn -- PFD outputs, feed the charge pump AND the real lock_detector
*            (design/netlist/lock_detector.spice) -- the design's OWN
*            phase-error window comparator is the lock criterion this bench
*            reads, not an externally-imposed threshold.
*
* Expects from the generated header (sim/lib/simenv.sh):
*   .lib <corner> / .temp <temp_c> / .param vsup=<V>
*   .param fref=<reference Hz>
*   .param bnd0v bnd1v bnd2v         VCO band-select bits (0 or vsup)
*   .param icp0v icp1v               PFD/CP Icp-trim bits (0 or vsup)
*   .param iunit=<A>                 CP bias reference unit current
*   .param sel0v..sel5v p0v..p5v     divider chain-length / modulus bits
*   .param vctrl_ic=<V>              initial condition on the control node --
*                                    0.9 or 2.7 (the usable-window rails) picks
*                                    cold-start vs. worst-case re-lock (see
*                                    run.sh); applied via a released clamp,
*                                    not a bare .ic (see below)
*   .param t_force=<s>               how long the vctrl_ic clamp holds after
*                                    t=0 before releasing (run.sh: a small
*                                    fraction of one reference period)
*   .param tstop tstep               transient window / print step, sized per N
*                                    in run.sh
*   .param tmax=<s>                  ceiling on the ngspice INTERNAL timestep
*                                    (.tran's 4th argument). Required, not
*                                    optional: run.sh passes
*                                    SIMENV_CLOSED_LOOP_TMAX. See the .tran
*                                    card below.
*   .param lockthresh=<V>            LOCK digital threshold (0.5*vsup)
* and expects "dut.spice" (sim/lib/assemble_closed_loop.sh's output) to have
* been copied into the run directory by testbench/run.sh.

.include "dut.spice"

*------------------------------------------------------------------ supplies
vdd    vdd    0 dc 'vsup'
vss    vss    0 dc 0
vddvco vddvco 0 dc 'vsup'
vddiv  vddiv  0 dc 'vsup'

*----------------------------------------------------------- reference clock
* 200 ps edges (not ideal steps) -- consistent with pfd-deadzone's stimulus,
* so this deck does not flatter the PFD's reset-path delay.
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

* Charge-pump bias reference -- ideal current sources at 4x the unit-leg
* current, exactly as sim/devchar-cp / sim/pfd-deadzone / sim/cp-compliance
* drive the same four nodes (bias generation is out of scope for cp.sch,
* see design/README.md).
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

* Break the ring's DC symmetry (see sim/vco-tuning-range/testbench/tb_vco_tuning.sp
* for the same technique and why `uic` is deliberately NOT used: the bias
* generator must settle to its own operating point before t=0).
.ic v(xvco.Y1)=0 v(xvco.Y2)='vsup' v(xvco.Y3)=0 v(xvco.Y4)='vsup' v(xvco.Y5)=0

* Control-node initial condition, WITHOUT `uic`. Vctrl has a well-determined
* DC operating point (it is DC-connected through the charge pump's output
* impedance and the filter's own resistor to ground), so a bare `.ic v(vctrl)`
* would only seed the op-point solver's Newton iteration and NOT survive into
* the transient -- op always converges to the same node voltage regardless of
* the seed. A hard, released clamp is used instead: a voltage-controlled
* switch ties VCTRL to 'vctrl_ic' through a low Ron for the op solve and the
* first 't_force' of the transient, then opens (Roff) and the loop runs
* freely from there. 'vctrl_ic' = 0.9 V (bottom of the usable window) selects
* cold start; 2.7 V (top) selects worst-case re-lock -- the largest excursion
* the loop could ever have to recover from, upper-bounding any real
* disturbance (reference retune within the band, supply glitch, coarse-band
* change) with a smaller one. See run.sh and this record's Methodology field.
vsetv vsetnode 0 dc 'vctrl_ic'
vsctrl sctrl 0 pulse('vsup' 0 't_force' 100p 100p '2*tstop' '4*tstop')
sforce vctrl vsetnode sctrl 0 SWFORCE
.model SWFORCE SW(Ron=10 Roff=1G Vt='vsup/2' Vh=0)

.options reltol=1e-3 abstol=1e-9 vntol=1e-4 chgtol=1e-13
* The 4th .tran argument (tmax) is LOAD-BEARING, not decoration: it is the
* ceiling on the ngspice INTERNAL timestep, set by the PFD's internal SR-latch
* set pulse (0.33-0.39 ns) and NOT by f_out. Omitting it -- as this deck did
* until #65 -- makes ngspice default the internal ceiling to the print step
* {tstep}, which run.sh sizes as 1/(50*f_out): 250 ps at this campaign's fixed
* 80 MHz target, coarse enough that the integrator runs pinned at the ceiling
* (measured mean internal step 0.230 ns) with barely one step inside the set
* pulse. See sim/lib/simenv.sh's SIMENV_CLOSED_LOOP_TMAX and sim/README.md's
* "Closed-loop internal-timestep bound" for why that misreports a locked loop
* as jammed-with-UP.
.tran {tstep} {tstop} 0 {tmax}

*------------------------------------------------------------- measurements
* The lock criterion is the DESIGN'S OWN lock_detector (design/README.md:
* "ERR = XOR(UP,DN); ERRD = ERR delayed t_win; WIDE = ERR.ERRD; assert is
* slow, deassert is fast"), not an externally-imposed frequency/phase
* threshold -- see this record's Methodology field for the derived
* frequency-settling-band statement this implies.
*
* Lock time = the LAST rising edge of LOCK in the simulated window. `rise=last`
* finds it directly; run.sh's tstop margin (>= lock_hold_cycles reference
* periods past the expected acquisition time) is what makes "last rise" mean
* "the rise that starts the final stable interval" rather than a mid-run
* chatter edge -- verified per point by the lockheld check below.
.measure tran t_lock_last_rise when v(lock)='lockthresh' rise=last
* Sanity: LOCK must still be asserted at the very end of the window (if this
* measurement is missing/low, the run needs a longer tstop -- flagged by
* run.sh, not silently accepted).
.measure tran lock_at_end find v(lock) at='tstop-1p'
* Final control-voltage reading, for the output-range-style margin check this
* record's Result table also reports incidentally (headroom to each rail).
.measure tran vctrl_final find v(vctrl) at='tstop-1p'

* Optional full-transient waveform capture (#49's Vctrl-anomaly prerequisite:
* the two .measure samples above give only the END-of-window state, not
* enough to distinguish a PFD/CP polarity effect, a SWFORCE-release
* switching artifact, or a genuine rail-stability question -- invoke via
* `run.sh --one <corner> <temp> <vdd> <n> <cond> <outcsv>` for a targeted
* single-point run). The sibling `sim/output-range` campaign's `lo`-edge
* anomaly-investigation record (same instrumentation, same prerequisite)
* has been completed; the equivalent `relock` investigation for THIS
* campaign has not yet been run to completion (attempted once; the run was
* still mid-transient after several hundred wall-clock seconds on a
* heavily-contended shared machine -- see #49's own throughput discussion
* for the measured ~4-8 ns simulated / CPU-s baseline this DUT gets even
* uncontended) and remains open follow-up scope. `wrdata` dumps the vectors ngspice
* already holds in memory after `run` completes -- no extra analysis cost,
* just file I/O -- so this is left ON unconditionally rather than gated
* behind a flag; ordinary corner-sweep runs simply produce (and, per
* run.sh, do not commit) one extra small CSV per run.
.control
run
wrdata waveform.csv v(vctrl) v(up) v(dn) v(lock) v(vwin)
.endc
.end
