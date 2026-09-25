* gf180-pll :: lock-window-proxy :: phase 'pads' -- the two pad-referred candidates
*
* A production tester cannot see t_win: ERR and ERRD are internal nodes of
* lock_detector and neither is a port of pll_top.  This deck measures the two
* quantities the existing pads DO expose that could stand in for it, in one
* transient at one PVT point, so they are directly comparable.
*
* CANDIDATE 1 -- the free-running ring period, T_vco.
*   VCTRL   pll_top iopin, forced to a DC level by the tester
*   B2:B0   pll_top ipins, the band code, held static
*   CLK     pll_top opin (a dedicated pad), counted by the tester
* Two operating points, because the ring is current-starved and its delay is
* not the same blend of nfet and pfet drive at every control voltage:
*   'a'  band 4, Vctrl = kvctrla -- mid band, mid control window
*   'b'  band 7, Vctrl = kvctrlb -- fastest band, top of the window
*
* CANDIDATE 2 -- the CLK -> FB pad skew, a digital propagation delay.
* design/netlist/pll_top.spice wires the divider chain's retiming flop as
*
*   XFRT DIVOUT VCO FB FBB VDD_DIV VSS dff_tg_3v3
*
* -- D = DIVOUT, CK = the VCO output, Q = FB.  Every FB edge is therefore one
* dff_tg_3v3 clock-to-Q delay after the CLK edge that produced it, and BOTH
* ends of that delay are pll_top output ports (CLK a dedicated pad, FB a
* digital test output).  A tester that triggers on CLK and times FB is
* measuring an on-die CMOS propagation delay built from the same 3.3 V
* inverters the trim cell's chain is built from -- no new pad, nothing
* internal exposed.
*
* The divider is clocked from ring 'a', exactly as pll_top clocks it from the
* VCO; CLK's only other load inside pll_top is the pad.  Divider configuration
* is SEL1 = 1 (one-hot, k = 2) with every P bit low, i.e. N = 4 -- the shortest
* legal modulus, so a short transient holds several FB edges.
*
* HOW THE SKEW IS RECOVERED.  FB rises only on a CLK rising edge, so a
* trig/targ between an arbitrary CLK rise and an arbitrary FB rise returns
* t_cq + k*T for an unknown non-negative integer k (k <= N-1 = 3 with the trig
* on the first CLK rise after the settling window).  The deck measures the
* period in the same transient and the reduction takes the remainder,
* t_cq = tcq_raw mod T.  That is exact, not approximate -- t_cq is by
* construction shorter than one CLK period -- and it removes any dependence on
* the divider's power-up phase, which is deterministic per deck but not per
* corner, since a faster corner fits more CLK edges into the same settling
* window.
*
* Startup.  A five-stage ring has no small-signal reason to leave its
* metastable DC point, so the odd/even nodes are seeded by .ic exactly as
* sim/vco-tuning-range's deck seeds them.  Everything is measured after
* ktsettle so neither the bias generator's start-up nor the divider's
* power-up transient is folded into a number.
*
* Expects from the harness-generated header:
*   .lib <process corner section>, .temp <temp_c>
*   .param vdd_val=<supply volts>  vdd_nom=<nominal volts>
*   .param kvctrla kvctrlb ktsettle ktstepv ktstopv

vddv vddvco 0 dc 'vdd_val'
vhi  bhi 0 dc 'vdd_val'
vca  vca 0 dc 'kvctrla'
vcb  vcb 0 dc 'kvctrlb'

* vco pin order: VCTRL B0 B1 B2 CLK VDD_VCO GND_VCO
* band 4 = B2:B1:B0 = 100
xva vca 0   0   bhi clka vddvco 0 vco
* band 7 = B2:B1:B0 = 111
xvb vcb bhi bhi bhi clkb vddvco 0 vco

* divider_chain pin order:
*   VCO P0 P1 P2 P3 P4 P5 SEL0 SEL1 SEL2 SEL3 SEL4 SEL5 DIVOUT FB VDD_DIV VSS
xdp clka 0 0 0 0 0 0 0 bhi 0 0 0 0 divouta fba vddvco 0 divider_chain

.ic v(xva.Y1)=0 v(xva.Y2)='vdd_val' v(xva.Y3)=0 v(xva.Y4)='vdd_val' v(xva.Y5)=0
.ic v(xvb.Y1)=0 v(xvb.Y2)='vdd_val' v(xvb.Y3)=0 v(xvb.Y4)='vdd_val' v(xvb.Y5)=0

.save v(clka) v(clkb) v(fba) v(divouta)
