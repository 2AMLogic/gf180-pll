* gf180-pll :: output-driver :: loaded output duty-cycle / levels-and-drive
* testbench (#144)
*
* WHAT THIS DECK MEASURES. spec/pll.md's "Verification owed" table lists two
* unmeasured rows for the buffered VCO output: Output duty cycle (target
* 45-55 % at CLK) and Output levels and drive (target V_OH >= 0.9*VDD_VCO,
* V_OL <= 0.1*VDD_VCO, driving <= 50 fF external load). Every frequency
* sim/vco-tuning-range has ever recorded is at CLK with essentially no load
* on it -- this deck is the first to put a representative load on CLK and
* read duty cycle and levels off the loaded waveform, plus the loaded 10-90 %
* edge rate as the drive-strength proxy (the same proxy sim/devchar-delay
* uses for its fan-out-1 chain: a stronger driver produces a faster edge into
* a fixed load capacitance).
*
* DUT: design/netlist/vco.spice's `vco` subcircuit (bias generator + 3-bit
* band-select mirror chain + 5-stage current-starved ring + 3-stage tapered
* output buffer + on-chip decap), the SAME block sim/vco-tuning-range
* characterizes, composed ahead of this fragment via tb.json's `dut` key.
* One instance only (unlike vco-tuning-range's seven-copies-per-deck
* topology): this campaign's independent variable is a `sweeps` axis (band +
* control voltage), not something worth co-simulating in one deck.
*
* LOAD NETWORK. `cload`, an ideal 50 fF capacitor from CLK to GND_VCO --
* spec/pll.md's own budget number ("<= 50 fF of external load plus the
* on-die divider input"). The on-die divider's own input capacitance is
* NOT separately added (see this record's Limitations): it is a real,
* additional load this deck does not model, so every number here is
* mildly optimistic relative to the assembled chip.
*
* OPERATING POINTS -- band0/Vctrl=0.9V and band7/Vctrl=2.7V, i.e. the two
* extremes of the ratified Vctrl window at the two extreme band codes, are
* the SAME fixed points sim/vco-tuning-range's own tb_vco_tuning.sp sweeps
* (see that deck's sw1hi/sw1lo/sw7hi/sw7lo output-swing measures) -- reused
* here rather than re-targeting the ratified 10/200 MHz band edges by
* per-corner interpolation, because the duty/level claim being tested is
* about the RING'S OWN edge-rate extremes (slowest starved edges at band0's
* floor, fastest at band7's ceiling), which is exactly what tb.json's
* `sweeps.edge` axis selects. spec/pll.md's own design basis for the duty
* target states the expected binding condition is "the bottom of the band,
* where the starved ring's internal edges are slowest" -- band0/Vctrl=0.9V
* IS that condition; band7/Vctrl=2.7V is the opposite extreme, included so
* the record brackets both ends rather than reporting only the expected
* worst case.
*
* Expects from the harness-generated header (see sim/harness/testbench.py):
*   vdd_val   supply for this PVT point        vdd_nom  nominal supply
*   temp_c    temperature for this PVT point (also applied via .temp)
* and from tb.json's `params` / `sweeps.edge`:
*   b0_code, b1_code, b2_code   VCO 3-bit band-select code (0 or 1 each)
*   vctrl                       fixed control voltage for this edge point
*   ktstep, ktstop, ktmax       transient controls, sized per edge point
*   tsettle                     bias/ring start-up time to exclude from
*                                every measurement window

.param cload=50f

*--------------------------------------------------------------------- bias
vvddvco vddvco 0 dc 'vdd_val'
vb0     b0     0 dc 'vdd_val*b0_code'
vb1     b1     0 dc 'vdd_val*b1_code'
vb2     b2     0 dc 'vdd_val*b2_code'
vvctrl  vctrl  0 dc 'vctrl'

*--------------------------------------------------------------------- DUT
xdut vctrl b0 b1 b2 clk vddvco 0 vco

*---------------------------------------------------------- external load
cload clk 0 'cload'

* Break the ring's DC symmetry so the operating point is not the metastable
* all-nodes-at-mid solution; the constraint is released when the transient
* starts. `uic` is deliberately NOT used: the bias generator must be solved
* to its operating point before t=0 -- same convention as
* sim/vco-tuning-range's tb_vco_tuning.sp.
.ic v(xdut.Y1)=0 v(xdut.Y2)='vdd_val' v(xdut.Y3)=0 v(xdut.Y4)='vdd_val' v(xdut.Y5)=0
