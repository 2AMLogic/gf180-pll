* gf180-pll :: divider-ratio-cell :: single div23_cell testbench (DR-001 Decision 3)
*
* Six independent copies of the SAME cell, so one transient covers every
* single-cell acceptance check at a given PVT point:
*
*   XA  P=0, 50% duty clock          -> divide by 2
*   XB  P=1, 50% duty clock          -> divide by 3   (MODIN tied high, i.e.
*                                       the chain-terminated last-cell case)
*   XC  P=0, 33% duty clock          -> divide by 2
*   XD  P=1, 67% duty clock          -> divide by 3
*   XE  P=1, clock at 1.5x kf        -> divide by 3   (speed margin)
*   XF  P=1, clock at 2.0x kf        -> divide by 3   (speed margin)
*
* XC / XD are the "both edges" check and they are not academic: a cell that is
* swallowing emits a 33%-duty CKOUT, and the 67% case is its complement, so
* every cell downstream of a swallowing cell is clocked by a duty-distorted
* waveform. Division must be exact for both, which is only true if the cell is
* purely rising-edge triggered.
*
* XE / XF quantify first-cell speed margin above the 200 MHz v1 ceiling
* (DR-002 Decision 2 budgets margin to the target, not the 400 MHz stretch);
* at kf = 200 MHz they are the 300 MHz and 400 MHz points.
*
* Running the same deck with a low kf (this manifest's 'rate' sweep axis,
* f200/f010) is the "no minimum clock frequency" check that DR-001 Decision 3
* requires of static CMOS -- it is the property dynamic/TSPC logic was
* rejected for, and it must hold at 125 C where leakage off a would-be
* dynamic node is worst.
*
* Fed by sim/harness: process/temp/vdd_val as usual, plus this manifest's
* 'rate' sweep axis params kf/ktstep/ktstop (derived per point -- see
* sim/harness/README.md "Sweeping beyond the PVT grid").
*
* div23_cell is composed ahead of this fragment by the manifest's 'dut' key
* (design/netlist/div23_cell.spice, exported from design/div23_cell.sch), so
* the frozen netlist snapshot is DUT + this file in one self-contained deck.

.param tvco='1/kf'
.param ttr='tvco/50'
.param ttd='tvco'
* 50% crossing of the first rising clock edge -- the phase reference used to
* extract clk->Q without depending on which edge index the output happens to
* land on.
.param tck0='ttd+ttr/2'

vdd vdd 0 dc 'vdd_val'
vhi hi 0 dc 'vdd_val'
vlo lo 0 dc 0

vck50 ck50 0 pulse(0 'vdd_val' 'ttd' 'ttr' 'ttr' 'tvco/2-ttr' 'tvco')
vck33 ck33 0 pulse(0 'vdd_val' 'ttd' 'ttr' 'ttr' 'tvco/3-ttr' 'tvco')
vck67 ck67 0 pulse(0 'vdd_val' 'ttd' 'ttr' 'ttr' '2*tvco/3-ttr' 'tvco')
vcke  cke  0 pulse(0 'vdd_val' 'ttd' 'ttr/1.5' 'ttr/1.5' 'tvco/3-ttr/1.5' 'tvco/1.5')
vckf  ckf  0 pulse(0 'vdd_val' 'ttd' 'ttr/2' 'ttr/2' 'tvco/4-ttr/2' 'tvco/2')

xa ck50 hi lo ckoa moa vdd 0 div23_cell
xb ck50 hi hi ckob mob vdd 0 div23_cell
xc ck33 hi lo ckoc moc vdd 0 div23_cell
xd ck67 hi hi ckod mdd vdd 0 div23_cell
xe cke  hi hi ckoe moe vdd 0 div23_cell
xf ckf  hi hi ckof mof vdd 0 div23_cell
