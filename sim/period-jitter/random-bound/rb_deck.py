"""gf180-pll :: period-jitter :: random-bound -- deck construction.

Builds the three kinds of deck this directory runs, and derives every one of
them from the committed `design/netlist/vco.spice` rather than from a
transcription of it.  See this directory's README.md for what the campaign
measures and, as importantly, for what it does not.

THE IDEA.  #520's option (B) is "a calibrated `trnoise()` injection ... it must
state up front which bias point each amplitude was calibrated at and bound the
error that stationary approximation costs".  This directory takes the bias
point to be **the maximum over the device's own trajectory**, which turns the
stationary approximation's error from a two-sided unknown into a one-sided,
provable over-estimate: the period variance a white generator produces is

    var(dT) = (1 / w0^2) * (1/2) * integral_cycle h(t)^2 S(t) dt

with `h(t)^2 >= 0`, so replacing `S(t)` by any `S_inj >= max_t S(t)` can only
raise it.  No ISF table is needed to use that fact -- the transient integrates
the true `h` itself -- and none of DR-031's reasons for refusing a
peak-|I_d| calibration applies to a maximum, because a maximum does not have to
be close to `S_eff` to bound it.  The flicker half is folded into the same
white injection by a second inequality; see `rb_extract.flicker_factor`.

THE THREE DECKS.

  1. TRAJECTORY: one clean VCO copy, `CLK` loaded by one real divider cell,
     with every VCO device's operating point saved -- the bias each device
     actually traverses.  Same construction as the transient deck's clean
     copy, so the trajectory the generators are evaluated along is the one the
     noise is later injected into.
  2. NOISE: every VCO device, standalone, at ONE trajectory timepoint, each in
     its own disjoint sub-network with its own ideal bias sources, sense
     resistor and 1 A AC probe, and `.noise` run once per device.  This is
     `../sid-trajectory/sid_deck.noise_deck` widened from one ring device to
     all 61 MOS devices of the VCO in one deck; the device lines are, as there,
     the committed netlist's own text.
  3. TRANSIENT: one clean reference copy and `ncopy` noisy copies of the whole
     VCO in ONE deck, each with a `trnoise()` current source across every
     MOS channel and every resistor, sized from deck 2's result.  The copies
     share only the ideal supply and control sources.

NOISE SOURCES ARE PLACED INSIDE DERIVED SUBCIRCUITS.  ngspice will not connect
a top-level element to a subcircuit's internal node (the ISF bring-up documents
that trap: `iinj 0 xa.Y1 ...` silently creates a new top-level node).  So the
noise elements are appended INSIDE derived copies of `vco_stage`, `vco_bias`
and `vco`, where the internal nets are in scope.  Every device line is the
committed netlist's own text; the derivation only renames the three
subcircuits, re-points their instance lines, and appends `in_<instance>`
current sources before `.ends`.  Each ring stage gets its OWN derived stage
subcircuit (`..._s1` .. `..._s5`) so that the five stages' amplitudes are
independent quantities rather than one shared assumption.
`sim/tests/test_random_bound.py` pins the derivation against the committed
netlist.
"""

from __future__ import annotations

import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ISF = HERE.parent / "isf-bringup"
if str(ISF) not in sys.path:
    sys.path.insert(0, str(ISF))

import isf_deck  # noqa: E402

#: Boltzmann constant, J/K -- CODATA 2019 exact value.
K_B = 1.380649e-23
T0_K = 273.15

STAGES = (1, 2, 3, 4, 5)
RING_DEVICES = ("XMPH", "XMP", "XMN", "XMNT")

#: The three subcircuits whose devices are noise sources, and the hierarchical
#: prefix each one's instances carry inside one `vco` copy.
BLOCKS = {
    "ring": "vco_stage",
    "bias": "vco_bias",
    "buffer": "vco",
}

_MOS_RE = re.compile(
    r"^(X\w+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+([np]fet_03v3)\s+(.*)$", re.I
)
_RES_RE = re.compile(r"^(X\w+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(ppolyf_u\w*)\s+(.*)$", re.I)


def kelvin(temp_c: float) -> float:
    return temp_c + T0_K


def _join_continuations(text: str) -> list[str]:
    out: list[str] = []
    for raw in text.splitlines():
        if raw.startswith("+") and out:
            out[-1] = out[-1].rstrip() + " " + raw[1:].strip()
        else:
            out.append(raw)
    return out


def subckt_lines(src: str, name: str) -> list[str]:
    """The body of `.subckt <name>`, continuations folded, header and `.ends` excluded."""
    lines = _join_continuations(src)
    body: list[str] = []
    inside = False
    for ln in lines:
        low = ln.strip().lower()
        if low.startswith(f".subckt {name.lower()} "):
            inside = True
            continue
        if inside and low.startswith(".ends"):
            return body
        if inside:
            body.append(ln.strip())
    raise ValueError(f"design/netlist/vco.spice: no `.subckt {name}` found")


def devices(src: str) -> list[dict]:
    """Every noise-generating device in one `vco` instance, with its hierarchical path.

    Returns a list of dicts: `path` (e.g. `xs3.xmn`, `xbias.xmp1`, `xmbp1`),
    `block` (`ring`/`bias`/`buffer`), `kind` (`mos`/`res`), `instance`,
    `stage` (ring only), the node names as the owning subcircuit writes them,
    `model` and the verbatim `params`.

    The MOS decoupling capacitors `XCDEC1/2` are deliberately NOT here: both
    terminals are `VDD_VCO`/`GND_VCO`, which every deck in this directory ties to
    ideal sources, so any noise they generate is shorted out.  That is stated in
    the README as a limit of the ideal-supply testbench, not hidden.

    Raises if the ring stage's device set is not the four this campaign knows,
    because a silent partial match would inject into three devices and report
    the ring.
    """
    out: list[dict] = []
    for block, sub in BLOCKS.items():
        for ln in subckt_lines(src, sub):
            m = _MOS_RE.match(ln)
            if m:
                inst = m.group(1).upper()
                rec = {
                    "block": block, "kind": "mos", "instance": inst,
                    "d": m.group(2), "g": m.group(3), "s": m.group(4),
                    "b": m.group(5), "model": m.group(6).lower(),
                    "params": m.group(7).strip(),
                }
                if block == "ring":
                    for s in STAGES:
                        out.append(dict(rec, stage=s, path=f"xs{s}.{inst.lower()}"))
                elif block == "bias":
                    out.append(dict(rec, path=f"xbias.{inst.lower()}"))
                else:
                    out.append(dict(rec, path=inst.lower()))
                continue
            m = _RES_RE.match(ln)
            if m:
                inst = m.group(1).upper()
                if block != "bias":
                    raise ValueError(
                        f"design/netlist/vco.spice: resistor {inst} outside "
                        "vco_bias -- this campaign only knows how to bias the "
                        "bias generator's resistors"
                    )
                out.append({
                    "block": block, "kind": "res", "instance": inst,
                    "n1": m.group(2), "n2": m.group(3), "n3": m.group(4),
                    "model": m.group(5).lower(), "params": m.group(6).strip(),
                    "path": f"xbias.{inst.lower()}",
                })
    ring = {d["instance"] for d in out if d["block"] == "ring"}
    if ring != set(RING_DEVICES):
        raise ValueError(
            "design/netlist/vco.spice: vco_stage's MOS set changed -- expected "
            f"{sorted(RING_DEVICES)}, found {sorted(ring)}"
        )
    return out


def op_vector(copy: int, path: str, param: str) -> str:
    """ngspice expression for one MOS operating-point vector of copy `copy`.

    The PDK's `nfet_03v3`/`pfet_03v3` are subcircuits wrapping a BSIM4 `m0`, so
    the model instance of `x<copy>.<path>` is `m.x<copy>.<path>.m0`.
    """
    return f"@m.x{copy}.{path}.m0[{param}]"


#: MOS operating-point vectors sampled along the trajectory.  `vgs/vds/vbs` are
#: what the standalone noise deck is biased at; `id/gm/gds` are what the
#: reproduction check compares.  Same set as `../sid-trajectory/`.
OP_VECTORS = ("vgs", "vds", "vbs", "id", "gm", "gds")

#: `vco_bias`'s ports as `vco` wires them, in the deck's own net names for one
#: copy of `vco_isf` (`x<k> vc bc0 bc1 bc2 clk<k> vdd 0 ...`).  Anything not in
#: this map is internal to `vco_bias` (`x<k>.xbias.<net>`) or to `vco`
#: (`x<k>.<net>`).
def _bias_net(copy: int, net: str) -> str:
    ports = {"VCTRL": "vc", "B0": "bc0", "B1": "bc1", "B2": "bc2",
             "VDD": "vdd", "VSS": "0",
             "VBP": f"x{copy}.vbp", "VBN": f"x{copy}.vbn"}
    return ports.get(net.upper(), f"x{copy}.xbias.{net.lower()}")


def resistor_vectors(dev: dict, copy: int = 0) -> tuple[str, str]:
    """The two terminal-voltage expressions of a bias-generator resistor."""
    def v(net):
        n = _bias_net(copy, net)
        return "0" if n == "0" else f"v({n})"
    return v(dev["n1"]), v(dev["n2"])


def trajectory_vectors(devs, copy: int = 0) -> list[str]:
    """`save`/`wrdata` column list for the trajectory deck, in a FIXED order.

    Order is `(device, param)` over `devs` as given, MOS then resistor
    terminals, and it is the contract with `rb_extract.read_trajectory`: `wrdata`
    writes no header, so columns are indexed by position.
    """
    cols: list[str] = []
    for d in devs:
        if d["kind"] == "mos":
            cols += [op_vector(copy, d["path"], p) for p in OP_VECTORS]
        else:
            for v in resistor_vectors(d, copy):
                if v != "0":
                    cols.append(v)
    return cols


# ---------------------------------------------------------------------------
# the noisy subcircuits
# ---------------------------------------------------------------------------
def trnoise_amplitude(s_one_sided: float, nt: float) -> float:
    """`trnoise(NA NT 0 0)` amplitude whose one-sided low-frequency PSD is `s_one_sided`.

    ngspice's `trnoise` draws an independent Gaussian of standard deviation
    `NA` every `NT` seconds and interpolates linearly between them.  That is an
    iid sequence convolved with a triangle of half-width `NT`, whose two-sided
    PSD is `NA^2 * NT * sinc^4(f NT)` -- `NA^2 * NT` at low frequency, so the
    ONE-sided density the rest of this directory uses is `2 NA^2 NT`.  The
    relation is not assumed: the `calibrate` stage measures it on this build,
    through an RC network with a closed-form variance.
    """
    if s_one_sided < 0:
        raise ValueError("a PSD cannot be negative")
    return math.sqrt(s_one_sided / (2.0 * nt))


def _noise_line(name: str, a: str, b: str, na: float, nt: float) -> str:
    return f"in_{name.lower()} {a} {b} trnoise({na:.6e} {nt:.6e} 0 0)"


def noisy_subckts(src: str, amps: dict, nt: float, tag: str = "") -> str:
    """Derived `vco_stage_rb{tag}_s<n>`, `vco_bias_rb{tag}` and `vco_rb{tag}`.

    `amps` maps every device `path` (see `devices`) to its `trnoise` amplitude
    in A; a missing path raises, because a silently noiseless device would make
    the result a lower bound presented as a bound.  An amplitude of exactly 0
    is an explicit "not injected here" (the bias generator, which is bounded by
    `bias_lti_deck` instead) and emits no source.  `tag` lets several amplitude
    variants coexist in one deck.

    `vco_rb{tag}` has `vco_isf`'s port list -- the ring nodes and each stage's
    `NH`/`NT` promoted -- so the transient deck gives every copy, clean or
    noisy, the same symmetry-breaking `.ic` the ISF bring-up uses.
    """
    devs = devices(src)
    missing = [d["path"] for d in devs if d["path"] not in amps]
    if missing:
        raise ValueError(f"no trnoise amplitude for {missing}")
    extra = set(amps) - {d["path"] for d in devs}
    if extra:
        raise ValueError(f"amplitudes given for unknown devices {sorted(extra)}")

    wrappers = isf_deck.derive_wrappers(src)
    stage_isf = re.search(r"^\.subckt vco_stage_isf\b.*?^\.ends\s*$", wrappers,
                          re.M | re.S).group(0)
    vco_isf = re.search(r"^\.subckt vco_isf\b.*?^\.ends\s*$", wrappers,
                        re.M | re.S).group(0)

    out: list[str] = []
    for s in STAGES:
        name = f"vco_stage_rb{tag}_s{s}"
        body = stage_isf.replace(".subckt vco_stage_isf ", f".subckt {name} ", 1)
        noise = [
            _noise_line(d["instance"], d["d"], d["s"], amps[d["path"]], nt)
            for d in devs if d["block"] == "ring" and d["stage"] == s
            and amps[d["path"]] > 0
        ]
        body = re.sub(r"^\.ends\s*$", "\n".join(noise) + "\n.ends", body,
                      count=1, flags=re.M)
        out.append(body)

    bias = "\n".join([f".subckt vco_bias_rb{tag} VCTRL B0 B1 B2 VBP VBN VDD VSS"]
                     + subckt_lines(src, "vco_bias"))
    noise = []
    for d in devs:
        if d["block"] != "bias":
            continue
        a, b = (d["d"], d["s"]) if d["kind"] == "mos" else (d["n1"], d["n2"])
        if amps[d["path"]] > 0:
            noise.append(_noise_line(d["instance"], a, b, amps[d["path"]], nt))
    out.append(bias + "\n" + "\n".join(noise) + "\n.ends")

    vco = vco_isf.replace(".subckt vco_isf ", f".subckt vco_rb{tag} ", 1)
    n_before = vco.count(" vco_stage_isf")
    for s in STAGES:
        vco, n = re.subn(rf"^(XS{s} .*) vco_stage_isf\s*$",
                         rf"\1 vco_stage_rb{tag}_s{s}", vco, flags=re.M)
        if n != 1:
            raise ValueError(f"could not re-point XS{s} in the derived vco")
    vco, n = re.subn(r"^(XBIAS .*) vco_bias\s*$", rf"\1 vco_bias_rb{tag}", vco,
                     flags=re.M)
    if n != 1 or n_before != len(STAGES):
        raise ValueError("could not re-point XBIAS / the stages in the derived vco")
    noise = [
        _noise_line(d["instance"], d["d"], d["s"], amps[d["path"]], nt)
        for d in devs if d["block"] == "buffer" and amps[d["path"]] > 0
    ]
    vco = re.sub(r"^\.ends\s*$", "\n".join(noise) + "\n.ends", vco, count=1,
                 flags=re.M)
    out.append(vco)
    return "\n".join(out) + "\n"


def _ports(copy: int) -> str:
    return " ".join(
        isf_deck.injection_net(cls, copy, s) for cls in ("Y", "NH", "NT")
        for s in STAGES
    )


def _ic(copy: int, offset: float = 0.0) -> str:
    """isf_deck.build_deck's symmetry-breaking initial condition.

    `offset` (V) is added to the first ring node's value only when a deck has
    to be re-run because the solver stalled at start-up (`run.py`'s startup
    retry): an oscillator forgets its initial condition within the settling
    time, and every quantity this directory reads is taken after it.  With the
    default 0.0 the line is exactly the ISF bring-up's.
    """
    def val(s):
        if s % 2:
            return f"{offset:g}" if (s == 1 and offset) else "0"
        return "'vsup'"
    return ".ic " + " ".join(f"v(y{copy}_{s})={val(s)}" for s in STAGES)


#: `div23_cell` mode pins held static for the CLK load: MODIN = P = 0 is the
#: cell's plain divide-by-two, so its two clocked flip-flops toggle and CLK sees
#: the same dynamic gate load it sees in `pll_top` on every cycle the cell is
#: not swallowing.
def _load(copy: int) -> str:
    return f"xld{copy} clk{copy} 0 0 ldo{copy} ldm{copy} vdd 0 div23_cell"


def _header(repo_root, pdk_models, op, src_label) -> list[str]:
    models = Path(pdk_models)
    net = Path(repo_root) / "design" / "netlist"
    return [
        f"* gf180-pll :: period-jitter :: random-bound -- {src_label}. GENERATED,",
        "* do not edit: sim/period-jitter/random-bound/rb_deck.py.",
        f'.include "{models / "design.ngspice"}"',
        *(f'.lib "{models / "sm141064.ngspice"}" {op[k]}'
          for k in ("mos_section", "res_section", "moscap_section")),
        f'.include "{net / "vco.spice"}"',
        f'.include "{net / "div23_cell.spice"}"',
    ]


def _sources(op) -> list[str]:
    out = [f".temp {op['temp_c']:g}",
           f".param vsup={op['vsup']:.6g} vc={op['vctrl']:.6g}",
           "vdd vdd 0 dc 'vsup'"]
    for i, bit in enumerate(op["band"]):
        out.append(f"vbc{i} bc{i} 0 dc '{int(bit)}*vsup'")
    out.append("vvc vc 0 dc 'vc'")
    return out


#: Same simulator options as `isf_deck.build_deck`'s default: the transient
#: deck's clean copy must integrate the ring exactly as the ISF bring-up and
#: `../sid-trajectory/` did.
OPTIONS = ("rshunt=1e12", "reltol=1e-4", "abstol=1e-15", "vntol=1e-7", "itl4=200")


def trajectory_deck(*, repo_root, pdk_models, op, devs, tstop, tstep, tmax,
                    kvco_dv: float, src=None, ic_offset: float = 0.0,
                    wrdata="traj.dat") -> tuple[str, list[str]]:
    """One clean VCO copy, CLK loaded, every device's operating point saved.

    Plus two more clean copies at `vctrl +/- kvco_dv` on their own control
    sources, so the VCO gain at this exact operating point is MEASURED on the
    same timestep sequence as the trajectory rather than read from another
    campaign's table.  The loop-filter bound needs it (`rb_extract.kt_over_c_bound`
    gives a voltage; `K_vco` turns it into a frequency).  Columns `v(clk1)`,
    `v(clk2)` follow `v(clk0)`.
    """
    if src is None:
        src = isf_deck.read_vco_netlist(repo_root)
    cols = ["v(clk0)", "v(clk1)", "v(clk2)"] + trajectory_vectors(devs)
    out = _header(repo_root, pdk_models, op, "trajectory deck")
    out.append(isf_deck.derive_wrappers(src).rstrip())
    out += _sources(op)
    out.append(f"vvcp vcp 0 dc {op['vctrl'] + kvco_dv:.9g}")
    out.append(f"vvcm vcm 0 dc {op['vctrl'] - kvco_dv:.9g}")
    out.append(f"x0 vc bc0 bc1 bc2 clk0 vdd 0 {_ports(0)} vco_isf")
    out.append(f"x1 vcp bc0 bc1 bc2 clk1 vdd 0 {_ports(1)} vco_isf")
    out.append(f"x2 vcm bc0 bc1 bc2 clk2 vdd 0 {_ports(2)} vco_isf")
    for k in (0, 1, 2):
        out.append(_load(k))
        out.append(_ic(k, ic_offset))
    out.append(".option " + " ".join(OPTIONS))
    out.append(".control")
    # `save` BEFORE `tran`, naming every column: an unsaved @m...[...] column
    # comes back frozen at its DC value (see isf_deck.build_deck).
    out.append("save " + " ".join(cols))
    out.append(f"tran {tstep:.6e} {tstop:.6e} 0 {tmax:.6e}")
    out.append("set wr_singlescale")
    out.append(f"wrdata {wrdata} " + " ".join(cols))
    out.append(".endc")
    out.append(".end")
    return "\n".join(out) + "\n", cols


def transient_deck(*, repo_root, pdk_models, op, variants, tstop, tstep, tmax,
                   rndseed: int, src=None, wrdata="clk.dat",
                   ic_offset: float = 0.0) -> tuple[str, list[dict]]:
    """Clean copy `x0` plus noisy copies, all in one deck.

    `variants` is a list of `(tag, amps, nt, ncopy)`: `ncopy` copies of
    `vco_rb<tag>` built with amplitudes `amps` and sample interval `nt`.  Several
    variants in ONE deck is how the `validate` stage compares amplitude and `NT`
    settings on a single adaptive timestep sequence.

    `rndseed` is set, but on this build it does NOT reproduce a `trnoise`
    realisation (the `validate` stage's `repeat` deck measures that), so a
    re-run reproduces the committed statistics, not the period sequences.

    Returns `(deck, copies)` where `copies[k]` describes copy `k`'s variant.
    """
    if src is None:
        src = isf_deck.read_vco_netlist(repo_root)
    out = _header(repo_root, pdk_models, op, "transient-noise deck")
    out.append(isf_deck.derive_wrappers(src).rstrip())
    copies = [{"copy": 0, "variant": "clean"}]
    seen = set()
    for tag, amps, nt, ncopy in variants:
        if tag in seen:
            raise ValueError(f"variant tag {tag!r} used twice")
        seen.add(tag)
        out.append(noisy_subckts(src, amps, nt, tag=tag).rstrip())
    out += _sources(op)
    out.append(f"x0 vc bc0 bc1 bc2 clk0 vdd 0 {_ports(0)} vco_isf")
    out.append(_load(0))
    out.append(_ic(0, ic_offset))
    k = 1
    for tag, _amps, nt, ncopy in variants:
        for _ in range(ncopy):
            out.append(f"x{k} vc bc0 bc1 bc2 clk{k} vdd 0 {_ports(k)} vco_rb{tag}")
            out.append(_load(k))
            out.append(_ic(k, ic_offset))
            copies.append({"copy": k, "variant": tag, "nt_s": nt})
            k += 1
    out.append(".option " + " ".join(OPTIONS))
    out.append(".control")
    out.append(f"set rndseed={int(rndseed)}")
    cols = " ".join(f"v(clk{c['copy']})" for c in copies)
    out.append(f"save {cols}")
    out.append(f"tran {tstep:.6e} {tstop:.6e} 0 {tmax:.6e}")
    out.append("set wr_singlescale")
    out.append(f"wrdata {wrdata} {cols}")
    out.append(".endc")
    out.append(".end")
    return "\n".join(out) + "\n", copies


# ---------------------------------------------------------------------------
# the multi-device noise deck
# ---------------------------------------------------------------------------
#: Band width of every `.noise` call, Hz.  With a 1 Hz band ngspice's integrated
#: plot IS the density; see `../sid-trajectory/sid_deck.NOISE_BANDWIDTH_HZ` for
#: the error an accidentally wider band produces, and the units anchor that
#: catches it (enforced here too).
NOISE_BANDWIDTH_HZ = 1.0


def polarity(dev: dict) -> float:
    """`+1` for an nfet, `-1` for a pfet: ngspice reports a pfet's `vgs/vds/vbs`
    in the device's own polarity, so a standalone pfet is biased with every
    terminal negated relative to its grounded source."""
    return -1.0 if dev["model"].startswith("p") else 1.0


def noise_deck(*, pdk_models, op, entries, freqs, rsense, combined: bool = True) -> str:
    """Every device at one trajectory timepoint, one `.noise` per frequency.

    `entries` is a list of `(j, dev, bias, offsets)`: `bias` is the in-situ
    `vgs/vds/vbs` (MOS, device polarity) or `v` (resistor, volts across it),
    and `offsets` the Newton-step corrections `run.py` computes from a first
    pass (`None` on the first pass).

    Every device sits in its OWN sub-network: its gate, bulk and drain are
    driven by their own ideal sources and only its source shares node 0.  An
    ideal source has zero impedance, so no device's generator reaches any
    other device's drain node, and a `.noise` referred to `v(d<j>)` sees device
    `j` and its sense resistor only.  That is what lets one deck and one
    operating point serve all 62 MOS devices, instead of 62 processes.

    `combined=True` (the default) goes one step further and runs ONE `.noise`
    per frequency, referred to the sum of every drain voltage (a stack of
    unit-gain VCVSs, which are noiseless).  Because the sub-networks are
    disjoint, device `j`'s generator reaches the sum only through `v(d<j>)`,
    with transimpedance `Z_m<j>`, so ngspice's per-device contribution
    `onoise_total.m.xm<j>.m0` in the summed analysis is exactly the one a
    `.noise` referred to `v(d<j>)` alone reports -- and the per-device units
    anchor (the sense resistor `rs<j>`, which also reaches the sum only through
    `v(d<j>)`) checks that on every device and every call.  It is 62 times
    fewer `.noise` analyses, each of which re-solves the whole deck's operating
    point.  `combined=False` is the per-device form `../sid-trajectory/` used,
    kept so a test can show the two agree.

    Resistors get NO `.noise`: the PDK models the poly body as a
    voltage-dependent expression, which ngspice turns into a behavioural source
    that `.noise` treats as NOISELESS (it reports only the ~33 Ohm terminal
    segments).  Their resistance is measured here (`V / I`) and their thermal
    density taken from `4 k T / R` in `rb_extract`, which is physics, not a
    model output.
    """
    models = Path(pdk_models)
    a: list[str] = []
    a.append("* gf180-pll :: period-jitter :: random-bound -- noise deck. GENERATED.")
    a.append(f'.include "{models / "design.ngspice"}"')
    a.append(f'.lib "{models / "sm141064.ngspice"}" {op["mos_section"]}')
    a.append(f'.lib "{models / "sm141064.ngspice"}" {op["res_section"]}')
    a.append(f".temp {op['temp_c']:g}")
    mos = []
    res = []
    for j, dev, bias, offsets in entries:
        off = offsets or {"vg": 0.0, "vd": 0.0, "vb": 0.0}
        if dev["kind"] == "mos":
            p = polarity(dev)
            a.append(f"vg{j} g{j} 0 dc {p * bias['vgs'] + off['vg']:.12e}")
            a.append(f"vb{j} b{j} 0 dc {p * bias['vbs'] + off['vb']:.12e}")
            a.append(f"vd{j} dd{j} 0 dc {p * bias['vds'] + off['vd']:.12e}")
            a.append(f"rs{j} dd{j} d{j} {rsense:.8e}")
            a.append(f"iprb{j} 0 d{j} dc 0 ac 1")
            a.append(f"xm{j} d{j} g{j} 0 b{j} {dev['model']} {dev['params']}")
            mos.append(j)
        else:
            a.append(f"vr{j} r{j} 0 dc {bias['v']:.12e}")
            a.append(f"xr{j} r{j} 0 0 {dev['model']} {dev['params']}")
            res.append(j)
    if combined and mos:
        prev = "0"
        for j in mos:
            a.append(f"esum{j} sum{j} {prev} d{j} 0 1")
            prev = f"sum{j}"
        out_node = prev
    a.append(".control")
    a.append("op")
    for j in mos:
        a.append("print " + " ".join(f"@m.xm{j}.m0[{p}]" for p in OP_VECTORS))
    for j in res:
        a.append(f"print i(vr{j})")
    n_noise = 0

    def _print(j):
        a.append(f"print onoise_total.m.xm{j}.m0 onoise_total.m.xm{j}.m0.1overf "
                 f"onoise_total.m.xm{j}.m0.id onoise_total_rs{j}_thermal")

    for f in freqs:
        a.append(f"ac lin 1 {f:.12g} {f:.12g}")
        a.append("print " + " ".join(f"mag(v(d{j}))" for j in mos))
        if combined and mos:
            n_noise += 1
            a.append(f"noise v({out_node}) iprb{mos[0]} lin 2 {f:.12g} "
                     f"{f + NOISE_BANDWIDTH_HZ:.12g} 1")
            a.append(f"setplot noise{2 * n_noise}")
            for j in mos:
                _print(j)
            continue
        for j in mos:
            n_noise += 1
            a.append(f"noise v(d{j}) iprb{j} lin 2 {f:.12g} "
                     f"{f + NOISE_BANDWIDTH_HZ:.12g} 1")
            a.append(f"setplot noise{2 * n_noise}")
            _print(j)
    a.append(".endc")
    a.append(".end")
    return "\n".join(a) + "\n"


# ---------------------------------------------------------------------------
# the bias generator, small-signal
# ---------------------------------------------------------------------------
#: Why the bias generator is not in the transient.  Its outputs VBP/VBN are
#: slow nets shared by all five stages, so a generator inside it moves the
#: ring's frequency for many periods after it acts -- the injected transient's
#: period sequence shows it as a POSITIVE lag-1 autocorrelation (+0.29 with
#: the bias generator alone, against -0.18 for the ring alone and -0.44 for
#: the buffer alone, at the reference point).  The flicker and loop factors
#: `rb_extract` applies to the transient assume a response no longer than
#: `1 + WINDOW_MARGIN` periods, which that memory breaks.  The bias generator
#: is quasi-DC (its devices' densities move by <= 0.22 dB over the cycle), so
#: it is analysed where it is exact: `.noise` about its DC operating point,
#: referred to the ring's instantaneous frequency through the two measured
#: static sensitivities `df/dV_BP` and `df/dV_BN`, and integrated with its own
#: flicker spectrum through the loop (`rb_extract.lti_period_variance`).


def ideal_bias_vco_subckt(src: str) -> str:
    """`vco_ib`: `vco_isf` with the bias generator removed and VBP/VBN as ports.

    Every line but `XBIAS` is `vco_isf`'s own, so the ring and buffer are the
    committed netlist's; only where VBP and VBN come from changes.
    """
    wrappers = isf_deck.derive_wrappers(src)
    vco_isf = re.search(r"^\.subckt vco_isf\b.*?^\.ends\s*$", wrappers, re.M | re.S).group(0)
    head, rest = vco_isf.split("\n", 1)
    body, n = re.subn(r"^XBIAS .*\n", "", rest, flags=re.M)
    if n != 1:
        raise ValueError("vco_isf: expected exactly one XBIAS line")
    head = head.replace(".subckt vco_isf ", ".subckt vco_ib ", 1) + " VBP VBN"
    return head + "\n" + body


def sensitivity_deck(*, repo_root, pdk_models, op, vbp: float, vbn: float, dv: float,
                     tstop, tstep, tmax, src=None, ic_offset: float = 0.0,
                     wrdata="sens.dat") -> tuple[str, list[str]]:
    """The ring's static frequency sensitivity to VBP and to VBN.

    Six clean copies in one deck, so one timestep sequence: `x0` the in-situ
    VCO (its own bias generator); `x1` the VCO with VBP/VBN held by ideal
    sources at `vbp`/`vbn` (the trajectory's cycle averages) -- which must
    reproduce `x0`'s frequency if the replacement is faithful; `x2`/`x3` with
    VBP at `vbp +/- dv`; `x4`/`x5` with VBN at `vbn +/- dv`.  Columns
    `v(clk0)` .. `v(clk5)`.
    """
    if src is None:
        src = isf_deck.read_vco_netlist(repo_root)
    out = _header(repo_root, pdk_models, op, "bias-sensitivity deck")
    out.append(isf_deck.derive_wrappers(src).rstrip())
    out.append(ideal_bias_vco_subckt(src).rstrip())
    out += _sources(op)
    levels = [(vbp, vbn), (vbp + dv, vbn), (vbp - dv, vbn), (vbp, vbn + dv), (vbp, vbn - dv)]
    out.append(f"x0 vc bc0 bc1 bc2 clk0 vdd 0 {_ports(0)} vco_isf")
    for k, (p, n) in enumerate(levels, start=1):
        out.append(f"vbp{k} bp{k} 0 dc {p:.9g}")
        out.append(f"vbn{k} bn{k} 0 dc {n:.9g}")
        out.append(f"x{k} vc bc0 bc1 bc2 clk{k} vdd 0 {_ports(k)} bp{k} bn{k} vco_ib")
    for k in range(len(levels) + 1):
        out.append(_load(k))
        out.append(_ic(k, ic_offset))
    cols = [f"v(clk{k})" for k in range(len(levels) + 1)]
    out.append(".option " + " ".join(OPTIONS))
    out.append(".control")
    out.append("save " + " ".join(cols))
    out.append(f"tran {tstep:.6e} {tstop:.6e} 0 {tmax:.6e}")
    out.append("set wr_singlescale")
    out.append(f"wrdata {wrdata} " + " ".join(cols))
    out.append(".endc")
    out.append(".end")
    return "\n".join(out) + "\n", cols


def bias_lti_deck(*, pdk_models, repo_root, op, src, kp: float, kn: float,
                  nh: dict, nt: dict, resistors: dict, kf_body: float, af_body: float,
                  freqs, first_pass: bool = False) -> str:
    """`.noise` of the bias generator about its DC point, referred to ring frequency.

    `vco_bias`'s own lines, in a derived `vco_bias_lti` whose only additions
    are, per poly resistor, the noise its body carries and `.noise` does not
    report (ngspice treats the PDK's voltage-dependent body as a noiseless
    behavioural source): a dummy resistor of the body's value, carrying the
    body's DC current so the card's own `KF |I|^AF / f` flicker applies (on
    all three segments, as `sid` counts it), whose short-circuit noise current
    a noiseless CCCS mirrors across the real resistor's terminals, with the
    mirrored DC current cancelled by an equal and opposite ideal source.
    `resistors` maps an instance name to `{"R_ohm", "I_A"}` (from `sid`).

    VBP and VBN are loaded as in the VCO: five `XMPH`-like pfets on VBP and
    five `XMNT`-like nfets on VBN, the committed device text, each drain held at
    that stage's cycle-average `NH`/`NT` voltage (`nh`/`nt`, by stage) -- so the
    nets see the ring's gate capacitance, and the loads' own channel noise
    flows into an ideal source and reaches nothing (it is in the transient).

    The output is `kp v(VBP) + kn v(VBN)`, in Hz: the ring's instantaneous
    frequency deviation.  One `.noise` per frequency over a 1 Hz band, so the
    integrated plot IS the density, with every contributor printed.
    `first_pass=True` omits the resistor dummies and the noise (an operating
    point only).
    """
    models = Path(pdk_models)
    devs = devices(src)
    a = [f"* gf180-pll :: period-jitter :: random-bound -- bias-generator LTI noise deck. GENERATED.",
         f'.include "{models / "design.ngspice"}"',
         f'.lib "{models / "sm141064.ngspice"}" {op["mos_section"]}',
         f'.lib "{models / "sm141064.ngspice"}" {op["res_section"]}']
    body = subckt_lines(src, "vco_bias")
    extra = []
    if not first_pass:
        for d in devs:
            if d["block"] != "bias" or d["kind"] != "res":
                continue
            r = resistors[d["instance"]]
            i = abs(r["I_A"])
            tag = d["instance"].lower()
            extra += [
                f"vd_{tag} da_{tag} {d['n2']} dc {i * r['R_ohm']:.9e}",
                f"rd_{tag} da_{tag} db_{tag} rbody_{tag} {r['R_ohm']:.9e}",
                f"vs_{tag} db_{tag} {d['n2']} dc 0",
                f"f_{tag} {d['n2']} {d['n1']} vs_{tag} 1",
                f"ic_{tag} {d['n1']} {d['n2']} dc {i:.9e}",
                f".model rbody_{tag} r (kf={3.0 * kf_body:.6e} af={af_body:.6g})",
            ]
    a.append(".subckt vco_bias_lti VCTRL B0 B1 B2 VBP VBN VDD VSS")
    a += body + extra
    a.append(".ends")
    # `.noise` needs an AC input to refer to; which one is irrelevant to the
    # output density this reads, and VCTRL is the natural one.
    a += [ln + " ac 1" if ln.startswith("vvc ") else ln for ln in _sources(op)]
    a.append("xb vc bc0 bc1 bc2 vbp vbn vdd 0 vco_bias_lti")
    ring = {d["instance"]: d for d in devs if d["block"] == "ring" and d["stage"] == 1}
    for s in STAGES:
        p, n = ring["XMPH"], ring["XMNT"]
        a.append(f"vlp{s} dlp{s} 0 dc {nh[s]:.9g}")
        a.append(f"xlp{s} dlp{s} vbp vdd vdd {p['model']} {p['params']}")
        a.append(f"vln{s} dln{s} 0 dc {nt[s]:.9g}")
        a.append(f"xln{s} dln{s} vbn 0 0 {n['model']} {n['params']}")
    a.append(f"eo1 o1 0 vbp 0 {kp:.9e}")
    a.append(f"eout out o1 vbn 0 {kn:.9e}")
    a.append(".control")
    a.append("op")
    a.append("print v(vbp) v(vbn)")
    if not first_pass:
        for k, f in enumerate(freqs, start=1):
            a.append(f"noise v(out) vvc lin 2 {f:.12g} {f + NOISE_BANDWIDTH_HZ:.12g} 1")
            a.append(f"setplot noise{2 * k}")
            a.append(f"echo @@f {f:.12g}")
            a.append("print all")
    a.append(".endc")
    a.append(".end")
    return "\n".join(a) + "\n"
