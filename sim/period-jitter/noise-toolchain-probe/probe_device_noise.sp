* Probe 3 of 4 -- does `.noise` report per-device, per-mechanism noise for the
* gf180mcu BSIM4 models?
*
* This is the probe that found something BETTER than the repository previously
* recorded. sim/period-jitter's records say a device-noise-equivalent figure
* "requires first calibrating the injected amplitude against a validated
* noise-PSD measurement of the VCO's dominant noise contributors". That reads
* as though the PSD itself were missing. It is not: ngspice's .noise analysis
* decomposes the result per device AND per mechanism, and the gf180mcu models
* populate every one.
*
* The DUT is the ring stage's switching nfet as drawn in design/netlist/vco.spice
* (`XMN Y A NT VSS nfet_03v3 L=0.28u W=2u nf=1`), biased at a fixed V_ds.
*
* `display` is the point of the deck: it lists the vectors the analysis
* produced, which is the evidence that the decomposition exists. The named
* prints then show the two mechanisms that matter for an oscillator --
* `.id` (channel thermal) and `.1overf` (flicker).
*
* UNITS, because DR-023 quotes these numbers. ngspice's noise2 (integrated)
* vectors are in V RMS, not V^2. Probe 4's runner checks that against theory:
* the 1 ohm sense resistor's own `onoise_total_rs_thermal` over a 1 Hz band
* must equal sqrt(4kTR*B) = 1.2875e-10, and it does to six figures. Squaring a
* number from this plot is therefore how a PSD is obtained from it.

.include "@DESIGN_NGSPICE@"
.lib "@MODELS_NGSPICE@" typical

vg  g  0  dc 1.65 ac 1
vd  dd 0  dc 1.65
rs  dd d  1
xm1 d g 0 0 nfet_03v3 W=2u L=0.28u nf=1 m=1

.control
op
* One 1 Hz band centred on 1 MHz: the integrated result over a 1 Hz bandwidth
* is numerically the spectral density at that frequency.
noise v(d) vg lin 2 1meg 1000001 1
echo "PROBE device_noise -- vectors produced by .noise:"
display
setplot noise2
echo "PROBE device_noise -- results:"
print onoise_total
print onoise_total_rs_thermal
print onoise_total.m.xm1.m0.id
print onoise_total.m.xm1.m0.1overf
.endc

.end
