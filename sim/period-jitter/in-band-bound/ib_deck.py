"""gf180-pll :: period-jitter :: in-band-bound -- deck construction.

Four kinds of deck, all derived from the committed `design/netlist/pll_top.spice`
rather than from a transcription of it.  See this directory's README.md for what
the campaign measures and for what it does not.

  1. DIGITAL.  The committed `pll_top`, with `VCTRL` held by an ideal source.
     That one substitution is the whole open-loop deck: the loop filter is
     still there and still loaded, the VCO still runs at this corner's 150 MHz
     control voltage, the divider still divides it, the PFD still compares, the
     charge pump still fires -- but the charge no longer moves `VCTRL`, so the
     reset window, the switch timing and every edge slew are measured at a
     fixed, known operating point.  No netlist surgery at all, so the DUT is
     the same `pll_top` the deterministic half of the row measures.
  2. CP NOISE.  The `cp` subcircuit alone, at the trim code this campaign runs
     (`CPB0 = CPB1 = 0`, one unit leg), in the state that matters: both
     switches fully on, which is the reset-window overlap, with the output held
     at this corner's control voltage through a sense resistor.  `.noise` once
     per frequency, per-device contributions printed, the sense resistor's own
     thermal noise as the units anchor.  A second call with both switches OFF
     measures what the other 95 % of the reference period contributes.
  3. CELLS.  Each logic cell type the three digital blocks instantiate,
     standalone, at its TRIP POINT, loaded by a deliberately generous
     capacitance -- `.noise` for the output-noise density that becomes edge
     jitter, and a transient with the slowest input ramp the digital deck
     measured anywhere, for the slew rate that divides it.  Disjoint
     sub-networks in one deck, ngspice's per-device breakdown separating them,
     the same construction `../random-bound/rb_deck.noise_deck` uses.
  4. CLK LOAD.  One real `div23_cell` -- the divider chain's first cell, which
     is `CLK`'s only load in `pll_top` -- with its clock input driven through a
     source resistance, `.noise` referred to that input node.  This is the one
     path that does not go through the loop, so it is measured separately and
     with only the DIVIDER's devices counted: the buffer driving `CLK` is
     `../random-bound`'s, already injected there, and must not be counted twice.

WHAT THE BIAS REFERENCES ARE.  `IBN`/`ICN`/`IBP`/`ICP` are ideal current
sources here, at `iunit = 8 uA`, exactly as `sim/period-jitter`,
`sim/reference-spur`, `sim/pll-top-smoke` and `sim/lock-time` drive them: the
bias generator is a separate, not-yet-designed block (design/README.md).  So no
noise from the current reference is in this bound -- a limitation this
directory's README states, not a modelling choice hidden here.
"""

from __future__ import annotations

import re
from pathlib import Path

#: Band width of every `.noise` call, Hz.  With a 1 Hz band ngspice's
#: integrated plot IS the density; `../sid-trajectory/sid_deck` documents the
#: error a wider band silently produces, and the units anchor catches it.
NOISE_BANDWIDTH_HZ = 1.0

MOS_MODELS = ("nfet_03v3", "pfet_03v3")

#: Simulator options.  The transient's are `sim/period-jitter/testbench/tb.json`'s
#: own, so this deck's converged solution is comparable with the deterministic
#: half's; `rshunt` is what the charge pump's disabled trim legs need.
TRAN_OPTIONS = ("rshunt=1e12", "itl4=200", "reltol=1e-3", "abstol=1e-13",
                "vntol=1e-6")
NOISE_OPTIONS = ("rshunt=1e12",)


def _join_continuations(text: str) -> list[str]:
    out: list[str] = []
    for raw in text.splitlines():
        if raw.startswith("+") and out:
            out[-1] = out[-1].rstrip() + " " + raw[1:].strip()
        else:
            out.append(raw)
    return out


def subckts(src: str) -> dict:
    """`{name: [line, ...]}` for every `.subckt` in the netlist, continuations folded."""
    out: dict[str, list[str]] = {}
    cur = None
    for ln in _join_continuations(src):
        s = ln.strip()
        low = s.lower()
        if low.startswith(".subckt "):
            cur = low.split()[1]
            out[cur] = []
        elif low.startswith(".ends"):
            cur = None
        elif cur is not None and s and not s.startswith("*"):
            out[cur].append(s)
    return out


def _model_of(tokens, known=None) -> str | None:
    """The model or subcircuit name on an instance line.

    Taken as the LAST token that is not a `key=value` parameter, never as the
    first token that happens to look like a known name: `divider_chain`'s first
    instance line is `XD0 VCO MI0 ...  div23_cell`, whose second token is the
    NET `VCO`, which is also the name of a subcircuit in the same file.
    Matching left to right would walk into the VCO from inside the divider.
    `known` is accepted and ignored, kept so callers read naturally.
    """
    for i in range(1, len(tokens)):
        last = i == len(tokens) - 1
        if last or "=" in tokens[i + 1]:
            return tokens[i].lower()
    return None


#: Leaf device models that are not MOS.  The four in-band blocks contain none
#: (`non_mos_devices` is asserted empty for each of them, so their MOS
#: enumeration is their complete generator set); `vco`'s poly resistors and the
#: loop filter's MIM capacitors are `../random-bound`'s business, not this
#: directory's.
NON_MOS_LEAF = ("ppolyf", "cap_", "rm", "nplus_u", "pplus_u")


def flatten_mos(src: str, top: str, prefix: str = "") -> list[str]:
    """Every MOS device inside `top`, as an ngspice hierarchical path.

    `prefix` is the path of the `top` instance itself (e.g. `xcp` or
    `xdut.xdiv`); the returned paths are what `@m.<path>.m0[...]` and
    `onoise_total.m.<path>.m0` name, because the PDK's `nfet_03v3`/`pfet_03v3`
    are subcircuits wrapping a BSIM4 `m0`.  Raises on an instance line whose
    model is neither a MOS nor a known subcircuit, so a netlist that grew a
    device family this campaign does not know cannot be silently half-counted.
    """
    subs = subckts(src)
    if top not in subs:
        raise ValueError(f"no `.subckt {top}` in the netlist")
    out: list[str] = []

    def walk(name: str, path: str):
        for ln in subs[name]:
            tok = ln.split()
            if not tok[0].lower().startswith("x"):
                continue
            model = _model_of(tok)
            inst = tok[0].lower()
            here = f"{path}.{inst}" if path else inst
            if model in MOS_MODELS:
                out.append(here)
            elif model in subs:
                walk(model, here)
            elif any(model.startswith(p) for p in NON_MOS_LEAF):
                continue
            else:
                raise ValueError(f"{name}: instance {tok[0]} has unknown model {model!r}")

    walk(top, prefix)
    return out


def non_mos_devices(src: str, top: str) -> list[str]:
    """Every non-MOS leaf device inside `top`, as a hierarchical path.

    Asserted empty for the charge pump, the PFD, the divider chain and the lock
    detector, which is what makes `flatten_mos` their COMPLETE generator set:
    if one of them ever grows a resistor or a capacitor, this campaign's device
    enumeration would silently stop covering it, and `sim/tests/test_in_band_bound.py`
    fails instead.
    """
    subs = subckts(src)
    out: list[str] = []

    def walk(name: str, path: str):
        for ln in subs[name]:
            tok = ln.split()
            if not tok[0].lower().startswith("x"):
                continue
            model = _model_of(tok)
            here = f"{path}.{tok[0].lower()}" if path else tok[0].lower()
            if model in MOS_MODELS:
                continue
            if model in subs:
                walk(model, here)
            else:
                out.append(f"{here} ({model})")

    walk(top, "")
    return out


def count_cells(src: str, top: str) -> dict:
    """How many instances of each leaf CELL `top` contains, recursively.

    A leaf cell is a subcircuit that instantiates only MOS devices.  This is
    the stage count the bound charges each block for (every stage, as if all of
    them sat in series in the block's timing path -- see `ib_extract`'s
    docstring), so it is derived from the netlist rather than typed in.
    """
    subs = subckts(src)
    leaf = {
        name for name, body in subs.items()
        if body and all(_model_of(ln.split(), subs) in MOS_MODELS
                        for ln in body if ln.split()[0].lower().startswith("x"))
    }
    counts: dict[str, int] = {}

    def walk(name: str):
        for ln in subs[name]:
            tok = ln.split()
            if not tok[0].lower().startswith("x"):
                continue
            model = _model_of(tok, subs)
            if model in MOS_MODELS:
                continue
            if model in leaf:
                counts[model] = counts.get(model, 0) + 1
            elif model in subs:
                walk(model)
            else:
                raise ValueError(f"{name}: unknown model {model!r}")

    walk(top)
    return dict(sorted(counts.items()))


# ---------------------------------------------------------------------------
# headers
# ---------------------------------------------------------------------------
def _lib_lines(pdk_models, op) -> list[str]:
    models = Path(pdk_models)
    out = [f'.include "{models / "design.ngspice"}"']
    for key in ("mos_section", "res_section", "moscap_section", "mimcap_section"):
        if op.get(key):
            out.append(f'.lib "{models / "sm141064.ngspice"}" {op[key]}')
    return out


def _header(pdk_models, op, repo_root, label: str, netlists=("pll_top.spice",)) -> list[str]:
    net = Path(repo_root) / "design" / "netlist"
    return [
        f"* gf180-pll :: period-jitter :: in-band-bound -- {label}. GENERATED,",
        "* do not edit: sim/period-jitter/in-band-bound/ib_deck.py.",
        *_lib_lines(pdk_models, op),
        *(f'.include "{net / n}"' for n in netlists),
        f".temp {op['temp_c']:g}",
    ]


# ---------------------------------------------------------------------------
# deck 1: the open-loop pll_top transient
# ---------------------------------------------------------------------------
#: The static configuration this campaign runs at, copied from
#: `sim/period-jitter/testbench/tb.json`'s `params` by `run.py` rather than
#: retyped here -- these names are the keys it must supply.
CONFIG_BITS = ("b0", "b1", "b2", "cpb0", "cpb1", "ldt0", "ldt1", "ldt2", "ldt3",
               "p0", "p1", "p2", "p3", "p4", "p5",
               "sel0", "sel1", "sel2", "sel3", "sel4", "sel5")

#: Nodes the digital deck writes out.  `UP`/`DN` give the reset window and the
#: charge-pump switch timing; `FB` the divider's output edge; `CLK` the output
#: and the divider's input; `REF` the stimulus; the divider chain's inter-cell
#: clocks, the PFD's reset-delay output and the lock detector's error and window
#: nodes, so the slew rates the bound uses are checked against nodes INSIDE the
#: blocks and not only at their boundaries.
#:
#: The divider's inter-cell clocks are named by the PARENT's nets (`CK1 .. CK6`
#: in `divider_chain`), not by the child's port (`xd1.ckout`): ngspice does not
#: alias a subcircuit port to the net connected to it, and `v(xdut.xdiv.xd1.ckout)`
#: is an unknown vector, which `print`/`wrdata` report as an error rather than
#: as a column of zeros.
def digital_columns(n_div_cells: int = 6) -> list[str]:
    cols = ["v(clk)", "v(fb)", "v(ref)", "v(vctrl)", "v(divout)", "v(lock)",
            "v(xdut.up)", "v(xdut.dn)", "v(xdut.xpfd.xpfd.rst_dly)",
            "v(xdut.xpfd.xpfd.nrst)", "v(xdut.xld.err)", "v(xdut.xld.wide)"]
    cols += [f"v(xdut.xdiv.ck{k})" for k in range(1, n_div_cells + 1)]
    cols += [f"v(xdut.xdiv.mo{k})" for k in range(5)]
    return cols


def digital_deck(*, pdk_models, repo_root, op, config, iunit: float, fref: float,
                 tstop: float, tstep: float, tmax: float, ref_edge: float = 200e-12,
                 columns=None, wrdata="dig.dat", r_hold: float = 1.0,
                 ref_delay: float | None = None,
                 gmin: float | None = None,
                 ic_offset: float = 0.0) -> tuple[str, list[str]]:
    """The committed `pll_top`, open loop: `VCTRL` held at this corner's lock point.

    Everything else -- the codes, the 8 uA references, the 200 ps reference
    edges, the ring's symmetry-breaking `.ic`, the solver options -- is
    `sim/period-jitter/testbench/tb_period_jitter.sp`'s, so the operating point
    the slew rates and the reset window are measured at is the operating point
    both halves of the Period jitter row are measured at.

    Holding `VCTRL` is what makes this deck cheap AND what makes it a
    measurement of the four blocks rather than of the loop: the quantities read
    off it (`t_on`, the switch-edge slews, the divider's output slew) are
    properties of the blocks at a fixed control voltage, and the loop's own
    response to them is applied afterwards, analytically, over every admissible
    loop at once.

    `r_hold` is why the hold is a source in series with 1 ohm and not a bare
    ideal source.  `loop_filter` puts `XCF5`, a 2 nF MIM capacitor, directly
    across `VCTRL`, so a bare ideal source there leaves that capacitor's branch
    current determined by nothing but the source's own -- and the solver stalls
    on it (`Timestep too small ... trouble with node "vvc#branch"`, reproducibly,
    once the charge pump starts switching).  One ohm in series makes the branch
    current well-posed and moves `VCTRL` by `I_cp * r_hold` ~ 2 uV, which is
    five orders below the 10 mV steps `../random-bound` measures `K_vco` over.
    The value is recorded with every result, and the `validate` stage re-runs at
    `100 * r_hold` to show the measurands do not depend on it.

    `ref_delay` is the reference pulse's own delay, in seconds.  It exists
    because the quantity this deck is here to measure -- how long the charge pump
    conducts into `VOUT` in one reference cycle -- is a property of the LOCKED
    PLL, and an open-loop deck's `REF` and `FB` sit at whatever relative phase
    the ring's free-running start-up leaves them at.  At an arbitrary phase the
    PFD asserts one output for the reset delay and the other for the reset delay
    PLUS the phase error, which is the wrong window by an order of magnitude.
    `run.py` therefore runs this deck twice: once to find where `FB`'s edges
    fall, then again with `ref_delay` set so `REF`'s edges coincide with them --
    which is the lock condition, and the only state in which the measured
    conduction window is the one the bound needs.  `None` keeps the unaligned
    default (half a reference period), which is the first pass.

    `gmin` raises ngspice's node-to-ground conductance above its 1e-12 default.
    It is `None` for every point that converges without it.  A minority of grid
    points abort the ALIGNED pass with `Timestep too small ... trouble with node
    "vsel<k>#branch"` -- a static configuration source whose net drives gates
    only, so its branch current is ~0 and the solver has nothing to scale its
    step against.  `itl4` up to 1000 and a tighter `reltol` do not help;
    `gmin = 1e-11` does.  It is a solver aid, not a circuit change (100 GOhm to
    ground at every node, against a 1 Ohm `VCTRL` hold and a 2 nF filter
    capacitor), and `run.py` records the value used at every point -- the same
    "record the deviation rather than hide it" treatment `../random-bound` gives
    the symmetry-breaking initial condition it has to move at one of its own
    points.

    `ic_offset` is that same move, and the second escalation axis.  The ring is
    started from an alternating `.ic` -- five nodes at 0 V and the supply -- and
    at one grid point (`ff`/125 °C/2.97 V) the resulting start-up transient makes
    the solver crawl at about 7.3 ns on a repeatedly halved timestep at every
    `gmin` in the ladder.  Lifting the three low nodes by `ic_offset` clears it,
    exactly as `../random-bound` clears the one point where its own deck stalls
    in its first nanosecond.  The oscillator forgets the offset well inside the
    60 ns of settling before anything is measured -- which the measured output
    frequency and divide ratio at that point are the evidence for -- and the
    offset used is recorded with the point.
    """
    if not 0.0 <= ic_offset < 0.5 * op["vsup"]:
        raise ValueError("the initial-condition offset must be a small positive bias")
    lo = f"{ic_offset:.6g}"
    if ref_delay is None:
        ref_delay_expr = "'0.5*tref'"
    else:
        if ref_delay <= 0:
            raise ValueError("the reference delay must be positive")
        ref_delay_expr = f"{ref_delay:.6e}"
    cols = list(columns or digital_columns())
    out = _header(pdk_models, op, repo_root, "open-loop pll_top digital deck")
    out += [
        f".param vsup={op['vsup']:.6g} vc={op['vctrl']:.6g} iunit={iunit:.6g}",
        f".param fref={fref:.6g} tref='1/fref'",
        "vdd vdd 0 dc 'vsup'",
        "vss vss 0 dc 0",
        "vgndvco gnd_vco 0 dc 0",
        f"vref ref 0 pulse(0 'vsup' {ref_delay_expr} {ref_edge:.4g} {ref_edge:.4g} "
        "'0.5*tref' 'tref')",
    ]
    for bit in CONFIG_BITS:
        if bit not in config:
            raise ValueError(f"the digital deck needs a `{bit}` configuration bit")
        out.append(f"v{bit} {bit} 0 dc '{int(config[bit])}*vsup'")
    out += [
        "iibn vdd ibn dc 'iunit'",
        "iicn vdd icn dc 'iunit'",
        "iibp ibp 0 dc 'iunit'",
        "iicp icp 0 dc 'iunit'",
        "vvc vchold 0 dc 'vc'",
        f"rvchold vchold vctrl {r_hold:.6g}",
        "xdut ref b0 b1 b2 cpb0 cpb1 ldt0 ldt1 ldt2 ldt3 p0 p1 p2 p3 p4 p5",
        "+ sel0 sel1 sel2 sel3 sel4 sel5 ibn icn ibp icp clk divout fb lock",
        "+ vctrl vdd vdd gnd_vco vdd vss pll_top",
        f".ic v(xdut.xvco.y1)={lo} v(xdut.xvco.y2)='vsup' v(xdut.xvco.y3)={lo}",
        f"+ v(xdut.xvco.y4)='vsup' v(xdut.xvco.y5)={lo}",
        ".option " + " ".join(TRAN_OPTIONS)
        + (f" gmin={gmin:.6g}" if gmin is not None else ""),
        ".control",
        "save " + " ".join(cols),
        f"tran {tstep:.6e} {tstop:.6e} 0 {tmax:.6e}",
        "set wr_singlescale",
        f"wrdata {wrdata} " + " ".join(cols),
        ".endc",
        ".end",
    ]
    return "\n".join(out) + "\n", cols


# ---------------------------------------------------------------------------
# deck 2: the charge pump's output-current noise
# ---------------------------------------------------------------------------
#: The two devices whose drain current IS the charge pump's output current: the
#: up and down output switches.  Named here so `run.py` prints their operating
#: point and the bound uses a MEASURED `I_cp`, not a nominal one.
CP_SWITCHES = ("xcp.xmswup", "xcp.xmswdn")


def cp_noise_deck(*, pdk_models, repo_root, op, src, freqs, rsense: float,
                  iunit: float, cpb0: int, cpb1: int, switches_on: bool) -> tuple[str, list[str]]:
    """`.noise` of `cp` alone, output held at this corner's control voltage.

    `switches_on=True` is the reset-window overlap: `UP` and `DN` both
    asserted, so both legs steer their current into `VOUT` (the `cp` netlist's
    `XMSWUP` is a pfet on `UPB`, `XMSWDN` an nfet on `DN`, so both are on with
    both inputs high).  That is the state whose density `gated_charge_spectrum`
    integrates over the overlap window.  `switches_on=False` is the rest of the
    reference period, where both legs are steered to the dump node and `VOUT`
    sees only the off switches -- measured, so the bound does not have to
    assume it is negligible.

    The output is held through `rsense`.  `rsense`'s own thermal noise, which
    ngspice reports separately, is both the units anchor AND the measurement of
    the node's transimpedance: its reported contribution is
    `sqrt(4 k T |Z|^2 / rsense)`, so dividing by `sqrt(4 k T rsense)` gives
    `|Z(f)|/rsense` at every frequency.  `run.py` recovers the short-circuit
    output current noise as `S_v/|Z|^2` with that measured `|Z|` -- NOT as
    `S_v/rsense^2`, which would be right only below the node's own corner and
    under-states the current noise by orders of magnitude above it.  The density
    the bound uses is the sum of the MOS devices' contributions only.
    """
    paths = flatten_mos(src, "cp", "xcp")
    lvl = "'vsup'" if switches_on else "0"
    out = _header(pdk_models, op, repo_root, "charge-pump output-noise deck")
    out += [
        f".param vsup={op['vsup']:.6g} vc={op['vctrl']:.6g} iunit={iunit:.6g}",
        f".param rs={rsense:.6g}",
        "vdd vdd 0 dc 'vsup'",
        f"vup up 0 dc {lvl}",
        f"vdn dn 0 dc {lvl}",
        f"vb0 b0 0 dc '{int(cpb0)}*vsup'",
        f"vb1 b1 0 dc '{int(cpb1)}*vsup'",
        "iibn vdd ibn dc 'iunit'",
        "iicn vdd icn dc 'iunit'",
        "iibp ibp 0 dc 'iunit'",
        "iicp icp 0 dc 'iunit'",
        "vsense vs 0 dc 'vc' ac 1",
        "rsense vs vout 'rs'",
        "xcp up dn b0 b1 ibn icn ibp icp vout vdd 0 cp",
        ".option " + " ".join(NOISE_OPTIONS),
        ".control",
        "op",
        "print v(vout) i(vsense) " + " ".join(f"@m.{p}.m0[id]" for p in CP_SWITCHES),
    ]
    for k, f in enumerate(freqs, start=1):
        out.append(f"noise v(vout) vsense lin 2 {f:.17g} "
                   f"{f + NOISE_BANDWIDTH_HZ:.17g} 1")
        # The k-th `noise` call creates plots `noise{2k-1}` (the spectrum) and
        # `noise{2k}` (the integral, which over a 1 Hz band IS the density).
        # Naming the call's own plot is not optional: `setplot noise2` on every
        # call re-reads the FIRST call and prints one density 45 times.
        out.append(f"setplot noise{2 * k}")
        out.append("print " + " ".join(
            f"onoise_total.m.{p}.m0 onoise_total.m.{p}.m0.1overf" for p in paths))
        out.append("print onoise_total_rsense_thermal")
    out += [".endc", ".end"]
    return "\n".join(out) + "\n", paths


# ---------------------------------------------------------------------------
# deck 3: the logic cells at their trip points
# ---------------------------------------------------------------------------
#: Every SINGLE-STAGE leaf cell the three digital blocks instantiate, with the
#: port order the committed netlist declares, which input carries the timing
#: edge, and the levels the cell's other inputs are held at so that input is the
#: one that switches.  `inverting` says whether tying the input to the output
#: finds a trip point (it does for every inverting single-path gate);
#: `tgate_3v3` is not a gain stage at all -- it is a pass gate, and its noise is
#: the thermal noise of its own channel charging the load, so it is biased
#: mid-supply and has no trip point.
#:
#: SINGLE-STAGE IS LOAD-BEARING, NOT DESCRIPTIVE.  `ib_extract.edge_jitter`'s
#: inequality -- that a stage's noise at the crossing is below its stationary
#: output-noise variance at its trip point -- is a statement about ONE gain
#: stage.  Self-biasing a MULTI-stage cell finds the bias at which its whole
#: cascade's gain is maximal, and the `.noise` there is the cascade's, which is
#: neither a bias the cell ever occupies nor a small-signal regime: `xor2_3v3`
#: (three `nand2_3v3` stages in series from A to Y) reports sigma_v = 0.87 V at
#: 27 C, against 4.1 mV for a single `pfdcp_inv_3v3`.  0.87 V is not a noise
#: voltage, it is a linearisation that has stopped being one.  So this table
#: holds only cells whose `.subckt` body is MOS devices alone, and a composite
#: cell is bounded as the composition of the single-stage cells along the path
#: through it (`ib_extract.TIMING_PATHS`).  `single_stage_cells` derives that set
#: from the netlist, and `sim/tests/test_in_band_bound.py` pins this table
#: against it, so a new composite cell cannot be added here by accident.
CELLS = {
    "pfdcp_inv_3v3":  dict(ports="A Y VDD VSS", inp="A", out="Y", statics={}, inverting=True),
    "inv_3v3":        dict(ports="A Y VDD VSS", inp="A", out="Y", statics={}, inverting=True),
    "inv2x_3v3":      dict(ports="A Y VDD VSS", inp="A", out="Y", statics={}, inverting=True),
    "schmitt_3v3":    dict(ports="A Y VDD VSS", inp="A", out="Y", statics={}, inverting=True),
    "pfdcp_nand2_3v3": dict(ports="A B Y VDD VSS", inp="A", out="Y",
                            statics={"B": "'vsup'"}, inverting=True),
    "nand2_3v3":      dict(ports="A B Y VDD VSS", inp="A", out="Y",
                           statics={"B": "'vsup'"}, inverting=True),
    "nand3_3v3":      dict(ports="A B C Y VDD VSS", inp="A", out="Y",
                           statics={"B": "'vsup'", "C": "'vsup'"}, inverting=True),
    "nor2_3v3":       dict(ports="A B Y VDD VSS", inp="A", out="Y",
                           statics={"B": "0"}, inverting=True),
    "tgate_3v3":      dict(ports="A Y GN GP VDD VSS", inp="A", out="Y",
                           statics={"GN": "'vsup'", "GP": "0"}, inverting=False),
}


def single_stage_cells(src: str) -> set:
    """Every `.subckt` in the netlist whose body is MOS devices alone.

    The criterion `CELLS` must agree with: a subcircuit that instantiates another
    subcircuit is a composition of gain stages, not one, and the trip-point
    inequality `ib_extract.edge_jitter` rests on does not apply to it.  Derived
    from the committed netlist so the two cannot drift apart.
    """
    subs = subckts(src)
    out = set()
    for name, body in subs.items():
        inst = [ln for ln in body if ln.split()[0].lower().startswith("x")]
        if inst and all(_model_of(ln.split()) in MOS_MODELS for ln in inst):
            out.add(name)
    return out


def _cell_instance(k: int, cell: str, in_node: str, out_node: str) -> str:
    spec = CELLS[cell]
    nodes = []
    for port in spec["ports"].split():
        if port == spec["inp"]:
            nodes.append(in_node)
        elif port == spec["out"]:
            nodes.append(out_node)
        elif port == "VDD":
            nodes.append("vdd")
        elif port == "VSS":
            nodes.append("0")
        else:
            nodes.append(f"s{k}_{port.lower()}")
    return f"xc{k} " + " ".join(nodes) + f" {cell}"


def _cell_statics(k: int, cell: str) -> list[str]:
    return [f"vs{k}_{p.lower()} s{k}_{p.lower()} 0 dc {v}"
            for p, v in CELLS[cell]["statics"].items()]


def cell_trip_deck(*, pdk_models, repo_root, op, cells) -> tuple[str, list[str]]:
    """Pass 1: each inverting cell self-biased (input tied to output) -> its trip point.

    Tying a single-path inverting gate's input to its own output puts it at the
    one voltage where its input and output agree, which is exactly its
    switching threshold, with no sweep and no interpolation.  The value is then
    handed to the `.noise` pass as a forced input, where it is a fixed point of
    the same network -- so the noise is measured at the bias the trip-point
    solve found, not near it.
    """
    names = [c for c in cells if CELLS[c]["inverting"]]
    out = _header(pdk_models, op, repo_root, "logic-cell trip-point deck")
    out += [f".param vsup={op['vsup']:.6g}", "vdd vdd 0 dc 'vsup'"]
    for k, cell in enumerate(names):
        out += _cell_statics(k, cell)
        out.append(_cell_instance(k, cell, f"y{k}", f"y{k}"))
        out.append(f"cl{k} y{k} 0 1f")
        out.append(f".nodeset v(y{k})={0.5 * op['vsup']:.6g}")
    out += [
        ".option " + " ".join(NOISE_OPTIONS),
        ".control", "op",
        "print " + " ".join(f"v(y{k})" for k in range(len(names))),
        ".endc", ".end",
    ]
    return "\n".join(out) + "\n", names


#: The units anchor every `.noise` deck in this directory carries: one resistor
#: whose short-circuit thermal noise reaches the output with unit gain, so every
#: call's reported figure can be checked against the closed form `4 k T R`
#: (`ib_extract.parse_noise_log` does it on every call, the same absolute check
#: `../random-bound` and `../sid-trajectory` apply).  `ANCHOR_SHUNT_OHM` only
#: gives the anchor node a DC path -- six orders above `ANCHOR_OHM`, so the
#: divider it forms is 1 to within a part per million.
ANCHOR_OHM = 1e3
ANCHOR_SHUNT_OHM = 1e9


def cell_noise_deck(*, pdk_models, repo_root, op, entries, freqs, cload: float,
                    src, anchor_ohm: float = ANCHOR_OHM) -> tuple[str, dict]:
    """Pass 2: `.noise` of each `(cell, bias)` in `entries`, one sub-network each.

    `entries` is a list of `(cell, bias_v, tag)`.  Each sub-network's input is
    an ideal DC source, so no sub-network's generators reach any other's output
    node, and the cell outputs are summed through unit-gain (noiseless) VCVSs so
    ONE `.noise` per frequency reports every cell separately in its own
    per-device contributions -- `../random-bound/rb_deck.noise_deck`'s
    construction, and the reason this whole stage costs seconds.

    `cload` is the load capacitance every cell is charged with.  It is
    deliberately generous: a stage's edge jitter is `sigma_v/SR`, and both
    `sigma_v ~ sqrt(1/C)` and `SR ~ 1/C`, so the jitter grows as `sqrt(C)` --
    a load larger than anything the design's fan-out presents makes the bound
    looser, never tighter.  The value used is recorded with every result.

    Returns `(deck, groups)` with `groups` mapping each entry's tag to the
    device paths whose contributions are that cell's output noise.
    """
    out = _header(pdk_models, op, repo_root, "logic-cell trip-point noise deck")
    out += [f".param vsup={op['vsup']:.6g} cl={cload:.6g}", "vdd vdd 0 dc 'vsup'"]
    groups: dict[str, list[str]] = {}
    for k, (cell, bias, tag) in enumerate(entries):
        out += _cell_statics(k, cell)
        # `vin0` carries the `ac 1` ngspice's `.noise` requires of its named
        # input source; without it every call aborts with `ac input not found`
        # and the per-device vectors come back zero-length.  Which source it is
        # does not affect the OUTPUT noise this stage uses -- only the
        # input-referred figure, which nothing here reads.
        out.append(f"vin{k} a{k} 0 dc {bias:.9g}" + (" ac 1" if k == 0 else ""))
        out.append(_cell_instance(k, cell, f"a{k}", f"y{k}"))
        out.append(f"cl{k} y{k} 0 'cl'")
        groups[tag] = flatten_mos(src, cell, f"xc{k}")
    out += [
        "vanch anch 0 dc 0",
        f"ranch anch anchy {anchor_ohm:.6g}",
        f"rashunt anchy 0 {ANCHOR_SHUNT_OHM:.6g}",
    ]
    prev = "0"
    for k in range(len(entries)):
        out.append(f"esum{k} sum{k} {prev} y{k} 0 1")
        prev = f"sum{k}"
    out.append(f"esumanch sumanch {prev} anchy 0 1")
    prev = "sumanch"
    out += [".option " + " ".join(NOISE_OPTIONS), ".control", "op",
            "print " + " ".join(f"v(y{k})" for k in range(len(entries)))]
    for k, f in enumerate(freqs, start=1):
        out.append(f"noise v({prev}) vin0 lin 2 {f:.17g} "
                   f"{f + NOISE_BANDWIDTH_HZ:.17g} 1")
        out.append(f"setplot noise{2 * k}")
        for tag in groups:
            out.append("print " + " ".join(
                f"onoise_total.m.{p}.m0 onoise_total.m.{p}.m0.1overf"
                for p in groups[tag]))
        out.append("print onoise_total_ranch_thermal")
    out += [".endc", ".end"]
    return "\n".join(out) + "\n", groups


def cell_slew_deck(*, pdk_models, repo_root, op, cells, cload: float,
                   in_slew: float, tstep: float, tmax: float,
                   wrdata="slew.dat") -> tuple[str, list[str]]:
    """Pass 3: each cell driven by the slowest input edge the digital deck measured.

    One ramp, `in_slew` volts per second, into every cell at once (each on its
    own instance, all sharing the one input source -- they do not interact
    through an ideal source).  The output's own slew at mid-supply, minimum
    over the rising and falling edge, is the `SR` that `edge_jitter` divides
    by.  Driving each cell with the slowest edge that occurs anywhere in the
    PFD, the divider chain or the lock detector, into a load larger than any
    the design presents, is what makes that `SR` a lower bound on the real one.
    """
    names = list(cells)
    swing = op["vsup"]
    tr = swing / in_slew
    out = _header(pdk_models, op, repo_root, "logic-cell slew deck")
    out += [
        f".param vsup={op['vsup']:.6g} cl={cload:.6g}",
        "vdd vdd 0 dc 'vsup'",
        f"vin a 0 pulse(0 'vsup' {2 * tr:.6e} {tr:.6e} {tr:.6e} {4 * tr:.6e} "
        f"{10 * tr:.6e})",
    ]
    for k, cell in enumerate(names):
        out += _cell_statics(k, cell)
        out.append(_cell_instance(k, cell, "a", f"y{k}"))
        out.append(f"cl{k} y{k} 0 'cl'")
    cols = ["v(a)"] + [f"v(y{k})" for k in range(len(names))]
    out += [
        ".option " + " ".join(TRAN_OPTIONS),
        ".control",
        "save " + " ".join(cols),
        f"tran {tstep:.6e} {8 * tr:.6e} 0 {tmax:.6e}",
        "set wr_singlescale",
        f"wrdata {wrdata} " + " ".join(cols),
        ".endc", ".end",
    ]
    return "\n".join(out) + "\n", names


# ---------------------------------------------------------------------------
# deck 4: what a block's INPUT GATES put back onto the node that drives them
# ---------------------------------------------------------------------------
#: The two gate-only loads of this campaign, each a block whose devices reach a
#: signal node only through their own gate capacitance -- so no channel of theirs
#: is connected to it, and their contribution is a back-coupling term rather than
#: a stage in a timing path.
#:
#:  * `clk` -- `div23_cell`'s clock input.  `CKIN` in `div23_cell` goes only to
#:    the two `dff_tg_3v3` clock inverters' gates (`XFQ`, `XFMO`), and `CLK` is
#:    at the same time the node this specification's period jitter is measured
#:    at, so this is the one path of the four blocks that does not pass through
#:    the loop and the one the `4 sin^2` weight does not suppress.
#:  * `up` -- `lock_detector`'s `XERR` (`xor2_3v3`) input.  The lock detector's
#:    ONLY inputs are `UP`/`DN` and its only output `LOCK` leaves `pll_top`
#:    without reaching any other instance (`ib_extract.connectivity_claim`
#:    checks exactly that), so it is in NO timing path at all: it can reach the
#:    output only by putting noise back onto `UP`/`DN`, which is what this deck
#:    measures.
#:
#: The driver itself is absent in both cases and replaced by a source resistance:
#: on `CLK` because the buffer driving it is `../random-bound`'s and its
#: generators must not be counted twice, on `UP` because its driver is the PFD's
#: own latch, already counted as a stage in `TIMING_PATHS`.
GATE_LOADS = {
    "clk": dict(cell="div23_cell", netlist="div23_cell.spice", node="clk",
                instance="xld clk 0 0 ldo ldm vdd 0 div23_cell",
                what="the divider chain's clock input, on CLK"),
    "up": dict(cell="xor2_3v3", netlist="pll_top.spice", node="up",
               instance="xld up ldb lderr vdd 0 xor2_3v3",
               statics=["vldb ldb 0 dc 0"],
               what="the lock detector's XOR input, on UP"),
}


def gate_load_deck(*, pdk_models, repo_root, op, src, freqs, r_drive: float,
                   load: str) -> tuple[str, list[str]]:
    """`.noise` on a driven node with one gate-only load on it.

    The node is driven through `r_drive` with its real driver absent (see
    `GATE_LOADS` for why, per load).  `r_drive` is NOT chosen as "the
    conservative one": because the load is capacitive, the transfer from a load
    device's noise to this node RISES with frequency until the node's own
    `r_drive * C_node` corner, so the resulting variance is not monotone in
    `r_drive` and `run.py` sweeps it and takes the maximum.  `r_drive`'s own
    thermal noise is the units anchor, exact at the bottom of the grid, and the
    density the bound uses is the sum of the LOAD's MOS devices only.
    """
    spec = GATE_LOADS[load]
    paths = flatten_mos(src, spec["cell"], "xld")
    node = spec["node"]
    out = _header(pdk_models, op, repo_root,
                  f"gate-load noise deck ({spec['what']})",
                  netlists=(spec["netlist"],))
    out += [
        f".param vsup={op['vsup']:.6g} rd={r_drive:.6g}",
        "vdd vdd 0 dc 'vsup'",
        f"vdrv drv 0 dc {0.5 * op['vsup']:.9g} ac 1",
        f"rdrv drv {node} 'rd'",
        *spec.get("statics", []),
        spec["instance"],
        ".option " + " ".join(NOISE_OPTIONS),
        ".control", "op", f"print v({node})",
    ]
    for k, f in enumerate(freqs, start=1):
        out.append(f"noise v({node}) vdrv lin 2 {f:.17g} "
                   f"{f + NOISE_BANDWIDTH_HZ:.17g} 1")
        out.append(f"setplot noise{2 * k}")
        out.append("print " + " ".join(
            f"onoise_total.m.{p}.m0 onoise_total.m.{p}.m0.1overf" for p in paths))
        out.append("print onoise_total_rdrv_thermal")
    out += [".endc", ".end"]
    return "\n".join(out) + "\n", paths
