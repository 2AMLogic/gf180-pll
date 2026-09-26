"""gf180-pll :: period-jitter :: ISF bring-up -- deck construction.

Builds the multi-copy charge-injection deck the impulse-sensitivity-function
(ISF, Hajimiri-Lee) bring-up measures Gamma with.  See this directory's
README.md for what the bring-up is for and, more importantly, for what it does
NOT establish.

THE ONE IDEA IN THIS FILE.  Gamma is a DIFFERENCE of two oscillator
trajectories -- one perturbed by an injected charge, one not -- and the
difference is 0.1-40 ps against a 6.7 ns period.  Running the two trajectories
as two separate ngspice processes would have them integrate on two
independently chosen adaptive timestep grids, and that grid difference alone is
the same order as the quantity being measured.  So every copy lives in ONE
deck: ngspice picks a single timestep sequence for the whole circuit, both
trajectories are integrated on it, and the grid error is common-mode and
differences out.  The copies share only the ideal supply node; they are
otherwise disjoint and cannot interact.
`sim/vco-tuning-range/testbench/tb_vco_tuning.sp` already uses the same
one-deck-many-copies construction for a different reason (seven control
voltages in one transient), so the pattern is not new here.

THE RING IS NOT RE-DRAWN HERE.  Charge injection needs a circuit element
connected to a ring node, and ngspice will not connect one to a subcircuit's
internal node: writing `iinj 0 xa.Y1 ...` is accepted silently and creates a
NEW top-level node named `xa.y1` instead, so the injection does nothing and the
run looks fine.  (Confirmed on the pinned ngspice-46 while bringing this up:
the measured period came back bit-identical with and without a 1 uA / 10 ps
injection that, had it connected, would have moved the node by volts.)  Rather
than hand-copy the ring into a testbench -- which would drift the moment
`design/vco.sch` changes -- this module DERIVES port-widened wrappers from the
committed `design/netlist/vco.spice` at deck-build time:

  * `vco_stage_isf` is `vco_stage` with its internal `NH` (pfet source / head
    current-source drain) and `NT` (nfet source / tail current-source drain)
    promoted to ports;
  * `vco_isf` is `vco` with the five ring nodes `Y1..Y5` and each stage's
    `NH`/`NT` promoted to ports, and its five stage instances re-pointed at
    `vco_stage_isf`.

Every device line is the committed netlist's own text, unmodified; the only
edits are to `.subckt` headers and to the five `XS*` instance lines.
`sim/tests/test_isf_bringup.py` pins that derivation against the committed
netlist, so a schematic change cannot silently desync it.
"""

from __future__ import annotations

import re
from pathlib import Path

#: Ring-internal node classes this bring-up can inject charge into, and what
#: the device noise generators attached to each one are.
INJECTION_NODES = {
    "Y": "stage output -- drain of both switching devices XMP/XMN",
    "NH": "pfet head node -- source of XMP, drain of the head source XMPH",
    "NT": "nfet tail node -- source of XMN, drain of the tail source XMNT",
}

_STAGES = (1, 2, 3, 4, 5)

#: Rise and fall time of the injection pulse, seconds.  Named rather than
#: inlined because the delivered charge depends on it -- see `injected_charge`.
RAMP_S = 1e-12


def injected_charge(amp: float, pw: float, tr: float = RAMP_S,
                    tf: float = RAMP_S) -> float:
    """Charge an ngspice `PULSE(0 amp TD TR TF PW PER)` element ACTUALLY delivers.

    ngspice's PULSE is a TRAPEZOID, not a rectangle: `PW` is the flat top and
    `TR`/`TF` are additional ramps on either side of it.  The area is therefore

        amp * (PW + TR/2 + TF/2)

    and NOT `amp * PW`.  This distinction is the whole reason this function
    exists: the first version of this deck set `amp = dq / pw`, which with
    `PW = 10 ps` and `TR = TF = 1 ps` delivered `1.10 * dq` and biased every
    reported `h` 10 % high (and every `h**2` 21 % high), because
    `isf_extract.sensitivity()` normalises by the NOMINAL `dq`.  The plateau
    amplitude on its own cannot reveal that error; only the area can, so the
    area is computed here and pinned by a test.
    """
    return amp * (pw + 0.5 * tr + 0.5 * tf)


def injection_amplitude(dq: float, pw: float, ramp: float = RAMP_S) -> float:
    """Pulse amplitude whose TRAPEZOIDAL area is exactly `dq`.

    Inverts `injected_charge` for `tr = tf = ramp`:
    `amp * (pw + ramp) == dq`.  Sizing the amplitude (rather than reporting the
    delivered charge as a separate quantity) keeps ONE charge number flowing
    through the reduction, the per-phase charge rules in `run.py`, the
    equal-charge guard in `isf_extract.node_differences` and the committed
    JSON -- so the nominal `dq` a row is normalised by is, by construction, the
    charge that row's copy received.
    """
    return dq / (pw + ramp)


def read_vco_netlist(repo_root) -> str:
    return (Path(repo_root) / "design" / "netlist" / "vco.spice").read_text()


def _subckt(src: str, name: str) -> str:
    m = re.search(rf"^\.subckt {re.escape(name)}\b.*?^\.ends\s*$", src, re.M | re.S)
    if not m:
        raise ValueError(f"design/netlist/vco.spice: no `.subckt {name}` found")
    return m.group(0)


def derive_wrappers(src: str) -> str:
    """`vco_stage_isf` + `vco_isf`, derived from the committed netlist text.

    Port-widening only: no device line is rewritten, no parameter is changed
    and no connection is altered.  Raises if the committed netlist's port order
    or stage count is not what this derivation assumes -- a loud failure is the
    point, since a silent one would inject charge into the wrong net.
    """
    stage = _subckt(src, "vco_stage")
    stage_hdr = stage.splitlines()[0].strip()
    if stage_hdr != ".subckt vco_stage A Y VDD VSS VBP VBN":
        raise ValueError(
            "design/netlist/vco.spice: vco_stage's port list changed -- expected "
            f"'.subckt vco_stage A Y VDD VSS VBP VBN', got {stage_hdr!r}"
        )
    stage_isf = stage.replace(
        stage.splitlines()[0],
        ".subckt vco_stage_isf A Y VDD VSS VBP VBN NH NT",
        1,
    )

    vco = _subckt(src, "vco")
    vco_hdr = vco.splitlines()[0].strip()
    if vco_hdr != ".subckt vco VCTRL B0 B1 B2 CLK VDD_VCO GND_VCO":
        raise ValueError(
            "design/netlist/vco.spice: vco's port list changed -- expected "
            "'.subckt vco VCTRL B0 B1 B2 CLK VDD_VCO GND_VCO', got "
            f"{vco_hdr!r}"
        )
    extra = " ".join(f"Y{s}" for s in _STAGES)
    extra += " " + " ".join(f"NH{s}" for s in _STAGES)
    extra += " " + " ".join(f"NT{s}" for s in _STAGES)
    vco_isf = vco.replace(
        vco.splitlines()[0],
        f".subckt vco_isf VCTRL B0 B1 B2 CLK VDD_VCO GND_VCO {extra}",
        1,
    )

    def _restage(line: str) -> str:
        m = re.match(r"^(XS(\d) (?:\S+ ){6})vco_stage\s*$", line)
        if not m:
            return line
        s = m.group(2)
        return f"{m.group(1)}NH{s} NT{s} vco_stage_isf"

    vco_isf = "\n".join(_restage(ln) for ln in vco_isf.splitlines())
    n = vco_isf.count("vco_stage_isf")
    if n != len(_STAGES):
        raise ValueError(
            f"design/netlist/vco.spice: expected {len(_STAGES)} `vco_stage` "
            f"instances inside `vco`, re-pointed {n}"
        )
    return stage_isf + "\n" + vco_isf + "\n"


def injection_net(cls: str, copy: int, stage: int) -> str:
    """The deck-level net name for node class `cls` of `stage` in `copy`."""
    if cls not in INJECTION_NODES:
        raise ValueError(
            f"unknown injection node class {cls!r} "
            f"(known: {sorted(INJECTION_NODES)})"
        )
    if stage not in _STAGES:
        raise ValueError(f"stage must be one of {_STAGES}, got {stage!r}")
    return f"{cls.lower()}{copy}_{stage}"


def injection_element(spec, copy: int, stage: int, name: str, t_inject, dq, pw) -> str:
    """One injection element line, for a node OR for a node PAIR.

    `spec` is either a node class (`"Y"`) or a 2-tuple of them
    (`("Y", "NT")`).

    A SINGLE node class injects charge `dq` into that node from ground.  That is
    the right stimulus for measuring `h` at the node, and it is the wrong
    stimulus for a device's channel noise: a MOSFET's channel generator is a
    current source between drain and source, which REMOVES charge from the drain
    and adds the same charge to the source.  A pair spec builds exactly that --
    `i<name> <drain> <source>`, whose positive current leaves the drain node and
    enters the source node -- so the measured phase shift is the two-terminal
    generator's own sensitivity, `h_ds`, with no subtraction anywhere.

    Why both exist.  `h_ds` is what the jitter sum needs, and by linearity it
    equals `h(drain) - h(source)`.  On this ring those two terms are nearly
    equal, so the difference is a small residue of two large numbers: measuring
    it as a difference costs ~20x in precision, while measuring it directly does
    not, and comparing the two constructions is the bring-up's own cross-check
    on whether the injection is landing where it is supposed to.

    CHARGE, not amplitude.  The amplitude is sized by `injection_amplitude` so
    the TRAPEZOID's area -- not its plateau times `pw` -- equals `dq`; see
    `injected_charge` for what goes wrong otherwise.
    """
    amp = injection_amplitude(dq, pw)
    ramp = f"{RAMP_S:.6e}"
    shape = (
        f"pulse(0 {amp:.8e} {t_inject:.8e} {ramp} {ramp} {pw:.6e} 1)"
    )
    if isinstance(spec, str):
        return f"i{name} 0 {injection_net(spec, copy, stage)} {shape}"
    drain, source = spec
    return (
        f"i{name} {injection_net(drain, copy, stage)} "
        f"{injection_net(source, copy, stage)} {shape}"
    )


def _ports(copy: int) -> str:
    return " ".join(
        injection_net(cls, copy, s) for cls in ("Y", "NH", "NT") for s in _STAGES
    )


def build_deck(
    *,
    repo_root,
    pdk_models,
    injections=(),
    ncopy: int,
    tstop: float,
    tstep: float,
    tmax: float,
    vctrl: float,
    vsup: float = 3.3,
    temp_c: float = 27.0,
    band=(0, 1, 1),
    mos_section: str = "typical",
    res_section: str = "res_typical",
    moscap_section: str = "moscap_typical",
    options=("rshunt=1e12", "reltol=1e-4", "abstol=1e-15", "vntol=1e-7", "itl4=200"),
    wrdata: str = "clk.dat",
    src: str | None = None,
    extra_vectors=(),
) -> str:
    """One ISF deck.

    `injections` is an iterable of `(copy, node_class, stage, t_inject, dq, pw)`.
    Copy 0 is the UNPERTURBED reference and must carry no injection.

    `extra_vectors` appends further ngspice vector expressions to the `wrdata`
    line, AND emits a `save` card naming them.  Both halves are required and the
    `save` is the load-bearing one: a device operating-point expression such as
    `@m.x0.xs1.xmn.m0[vgs]` that is only named on `wrdata` comes back FROZEN at
    its DC value for every timepoint -- the column varies not at all, the run
    exits 0, and nothing announces it.  Only a vector listed on a `save` before
    the `tran` is tracked through the transient.

    Additive by construction: with the default empty tuple the generated deck is
    byte-identical to what it was before this parameter existed, so the ISF
    bring-up's own committed evidence is unaffected.  It exists so that
    `sim/period-jitter/sid-trajectory/` can sample the ring's bias trajectory
    out of *this* deck -- the same construction, options, initial conditions and
    therefore the same adaptive timestep sequence the committed `h(x)` table was
    measured on -- rather than out of a second, nominally-equivalent one.
    """
    if src is None:
        src = read_vco_netlist(repo_root)
    models = Path(pdk_models)
    out: list[str] = []
    a = out.append
    a("* gf180-pll :: period-jitter :: ISF bring-up -- GENERATED, do not edit.")
    a("* Generated by sim/period-jitter/isf-bringup/isf_deck.py; see that")
    a("* directory's README.md for what this deck is and is not evidence for.")
    a(f'.include "{models / "design.ngspice"}"')
    for sec in (mos_section, res_section, moscap_section):
        a(f'.lib "{models / "sm141064.ngspice"}" {sec}')
    a(f'.include "{Path(repo_root) / "design" / "netlist" / "vco.spice"}"')
    a(derive_wrappers(src).rstrip())
    a(f".temp {temp_c:g}")
    a(f".param vsup={vsup:.6g} vc={vctrl:.6g}")
    a("vdd vdd 0 dc 'vsup'")
    for i, bit in enumerate(band):
        a(f"vbc{i} bc{i} 0 dc '{int(bit)}*vsup'")
    a("vvc vc 0 dc 'vc'")

    for k in range(ncopy):
        a(f"x{k} vc bc0 bc1 bc2 clk{k} vdd 0 {_ports(k)} vco_isf")
        # Break the ring's DC symmetry so the operating point is not the
        # metastable all-nodes-at-mid solution, exactly as
        # sim/vco-tuning-range/testbench/tb_vco_tuning.sp does.  Every copy
        # gets the IDENTICAL initial condition: the copies must be
        # indistinguishable until the injection, or the difference this deck
        # measures is not the injection's.
        ic = " ".join(
            f"v(y{k}_{s})={'0' if s % 2 else chr(39) + 'vsup' + chr(39)}"
            for s in _STAGES
        )
        a(f".ic {ic}")

    seen = set()
    for (copy, spec, stage, t_inject, dq, pw) in injections:
        if copy == 0:
            raise ValueError("copy 0 is the reference and carries no injection")
        if copy in seen:
            raise ValueError(f"copy {copy} carries more than one injection")
        if not 0 < copy < ncopy:
            raise ValueError(f"injection copy {copy} outside 1..{ncopy - 1}")
        seen.add(copy)
        a(injection_element(spec, copy, stage, f"inj{copy}", t_inject, dq, pw))
    a(".option " + " ".join(options))
    a(".control")
    cols = [f"v(clk{k})" for k in range(ncopy)]
    extra = [str(v) for v in extra_vectors]
    if extra:
        # MUST precede the `tran`, and MUST name every column: see the
        # docstring -- an unsaved @m...[...] column is silently constant.
        a("save " + " ".join(cols + extra))
    a(f"tran {tstep:.6e} {tstop:.6e} 0 {tmax:.6e}")
    a("set wr_singlescale")
    a(f"wrdata {wrdata} " + " ".join(cols + extra))
    a(".endc")
    a(".end")
    return "\n".join(out) + "\n"
