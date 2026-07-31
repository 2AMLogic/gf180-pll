* gf180-pll :: mc-cp-mismatch :: DC UP/DN current mismatch, RANDOM device
* mismatch enabled (Monte Carlo)
*
* DUT: `cp` from the same xschem hierarchy sim/cp-compliance/testbench/
* tb_cp_dc.sp uses (netlisted via design/netlist.sh --top pfd_cp, included
* below as dut.spice). This deck measures the SAME quantity as tb_cp_dc.sp's
* term-1 mismatch (Iup-Idn)/Iavg -- but with `sw_stat_mismatch=1` instead of
* tb_cp_dc.sp's `0`. tb_cp_dc.sp measures the SYSTEMATIC mismatch (finite,
* unequal ro between the two polarities, corner-swept); this deck adds the
* gf180mcu per-instance RANDOM Vth/mobility mismatch model (`agauss()` inside
* every `nfet_03v3_dss`/`pfet_03v3_dss`, gated by `sw_stat_mismatch`) on top
* of that same systematic baseline, at ONE nominal PVT point -- corner
* sensitivity of the MEAN is tb_cp_dc.sp's job, not this campaign's (see
* run.sh's header for the full justification and the model-capability
* evidence).
*
* Deliberately ONE UP/DN pair per invocation, not several in parallel: an
* earlier version of this deck ran several mismatched replicas in one
* ngspice invocation to amortize the model-file parse cost, and hit
* `Timestep too small` convergence failures scaling with replica count
* (the shared VDD/VSS rails feeding N independent cp_dumpbuf op-amp pairs)
* that neither raising `itl1`/`itl4` nor `gmin` stepping resolved inside a
* practical wall-clock budget. run.sh instead runs many single-instance
* invocations at different `.option rndseed` values -- exactly tb_cp_dc.sp's
* own topology, already proven across 45 corners x 4 trim codes, plus one
* seed. This makes each invocation reliable at the cost of more of them.
*
* Measured at the three Vctrl window points tb_cp_dc.sp's systematic record
* reports (0.9 / 1.65 / 2.4 V) via `alter` + `op`, not a continuous DC sweep:
* a Monte Carlo sample does not need the full I-V curve, only the mismatch at
* the points the budget table states.
*
* Expects from the generated header (see sim/lib/simenv.sh):
*   .lib <process corner section>   typical, for this campaign (nominal PVT
*                                   only -- see run.sh's header)
*   .temp <temp_c>
*   .param vsup=<supply volts>
*   .param sw_stat_mismatch=1       (run.sh passes this; sw_stat_global stays
*                                   at design.ngspice's default 0 -- mismatch
*                                   only, exactly sim/README.md's worked
*                                   distribution example)
*   .option rndseed=<seed>          (run.sh passes this via simenv_run_deck's
*                                   special-cased kv; see sim/lib/simenv.sh)
* and expects `dut.spice` (the xschem export of design/, same file
* cp-compliance and pfd-deadzone use) to have been copied into the run
* directory by testbench/run.sh.

.include "dut.spice"

* Ideal bias references, exactly as tb_cp_dc.sp: bias generation is a
* separate block (design/README.md), and driving it ideally keeps the
* measured mismatch the output stage's (+ cp_dumpbuf's) own.
.param iunit=8u
* Nominal trim code, same as pfd-deadzone: b1 b0 = 1 0 -> 3 unit legs.
.param b0_code=0
.param b1_code=1

.csparam vsup_c={vsup}

vdd vdd 0 dc 'vsup'
vss vss 0 dc 0
* Swept output node, shared by both polarities (as tb_cp_dc.sp).
vsw sw 0 dc 0
vhi hi 0 dc 'vsup'
vlo lo 0 dc 0
vb0 b0 0 dc 'vsup*b0_code'
vb1 b1 0 dc 'vsup*b1_code'

*---------------------------------------------------------- UP-only instance
xcpu hi lo b0 b1 ibn_u icn_u ibp_u icp_u d_up vdd vss cp
iibn_u vdd ibn_u dc 'iunit'
iicn_u vdd icn_u dc 'iunit'
iibp_u ibp_u 0 dc 'iunit'
iicp_u icp_u 0 dc 'iunit'
vam_up d_up sw 0

*---------------------------------------------------------- DN-only instance
xcpd lo hi b0 b1 ibn_d icn_d ibp_d icp_d d_dn vdd vss cp
iibn_d vdd ibn_d dc 'iunit'
iicn_d vdd icn_d dc 'iunit'
iibp_d ibp_d 0 dc 'iunit'
iicp_d icp_d 0 dc 'iunit'
vam_dn sw d_dn 0

*------------------------------------------------------------------- analysis
.option abstol=1e-14 reltol=1e-4 vntol=1e-7 rshunt=1e12
.control
  set noaskquit
  alter vsw = 0.9
  op
  echo "MCDC_LO iup=$&i(vam_up) idn=$&i(vam_dn)"
  alter vsw = 1.65
  op
  echo "MCDC_MID iup=$&i(vam_up) idn=$&i(vam_dn)"
  alter vsw = 2.4
  op
  echo "MCDC_HI iup=$&i(vam_up) idn=$&i(vam_dn)"
.endc
