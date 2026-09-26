"""gf180-pll :: period-jitter :: S_id-along-the-trajectory -- deck construction.

Builds the two decks this directory needs, and derives BOTH of them from the
committed `design/netlist/vco.spice` rather than from a transcription of it.
See this directory's README.md for what the campaign is for and, more
importantly, for what it does NOT establish.

THE TWO DECKS, AND WHY THEY ARE A PAIR.

  1. THE TRAJECTORY DECK is the ISF bring-up's own reference deck.  It is not
     re-derived here: `trajectory_deck()` calls
     `sim/period-jitter/isf-bringup/isf_deck.build_deck()` with `ncopy=1` and no
     injection -- byte-for-byte the deck that directory's `period` stage runs --
     and only adds a `save`/`wrdata` column list.  That matters because the
     phase axis of the committed `h(x)` table is `t = T_INJECT0 + x * T` on
     *that* deck's own adaptive timestep sequence; sampling the bias trajectory
     out of a second, nominally-equivalent deck would put the two ingredients of
     the jitter sum on two phase axes whose relative offset nobody measured.

  2. THE NOISE DECK is one ring device, alone, biased at a `(V_gs, V_ds, V_bs)`
     triple lifted off that trajectory, with `.noise` run on it.  Its device
     line is the committed netlist's OWN TEXT for that instance
     (`device_line()`), not a hand-written `nfet_03v3 W=2u L=0.28u`: the drawn
     `ad`/`as`/`pd`/`ps`/`nrd`/`nrs`/`sa`/`sb`/`sd` set the terminal-resistance
     noise generators and the stress/geometry corrections to the channel ones,
     so a hand-written line measures a different device than the ring contains.
     `sim/period-jitter/noise-toolchain-probe/probe_sid_bias.sp.in` does write
     the line by hand, correctly for what it is (a 1-D existence probe); this
     directory cannot.

WHAT THE NOISE DECK MEASURES, AND HOW IT IS NORMALISED.  `.noise` reports the
per-device, per-mechanism contribution to the OUTPUT voltage.  The pipeline
needs the generator's own DRAIN-CURRENT PSD, so the deck carries a 1 A AC
current source between drain and source purely to measure the transimpedance
`Z_m = |v(d)|` from a drain-to-source current to the output node, and the
reduction divides by it.  Two independent normalisations fall out of the same
run and are compared in `sid_extract.extract_noise()`:

  * `S_id = (onoise_total.<gen> / Z_m)**2` -- the output vector over the
    measured transimpedance, and
  * `S_id = inoise_total.<gen>**2` -- ngspice's own input-referred vector,
    which because the input source IS that drain-to-source current source is
    already the quantity wanted.

They must agree; that they do (and to how many digits) is committed evidence
rather than an assumption about what `inoise_total` means.

THE SENSE RESISTOR IS PRE-COMPENSATED, NOT ASSUMED SMALL.  The output node is
the drain of a device whose drain is fed through a sense resistor `R`, so the
device sees `V_ds - I_d * R`, not `V_ds`, and the same is true of the device's own
`rd`/`rs`.  `noise_deck()` takes three offsets for that, and `run.py` sets them by
a Newton step on the OBSERVED bias residual rather than from a closed form -- see
`noise_deck`'s own docstring for the sign that makes the closed form unsafe, and
for the 1e-3-class residual it leaves when the sign goes the wrong way.  That is
the same size as several of the differences this directory reports, and a check
that cannot resolve what it is checking is not a check.
"""

from __future__ import annotations

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
#: 0 degC in kelvin.
T0_K = 273.15

#: The four devices of `vco_stage`, in the order a reader of the schematic meets
#: them, with what each one is and which of its terminals the ring node is.
#:
#: These are the ring's noise-injection points as far as the ISF bring-up's
#: `h_gen` measurement can weight them: `Y`-`NT` and `Y`-`NH` are the two
#: switching devices' channel generators, `NH`-`VDD` and `NT`-`VSS` the two
#: current sources'.  The bias generator's own devices are NOT here -- see the
#: README's "What this does NOT establish".
RING_DEVICES = {
    "XMPH": "pfet head current source -- gate on VBP, drain is the pfet head node NH",
    "XMP": "switching pfet -- gate on the stage input A, drain is the stage output Y",
    "XMN": "switching nfet -- gate on the stage input A, drain is the stage output Y",
    "XMNT": "nfet tail current source -- gate on VBN, drain is the nfet tail node NT",
}

#: Device operating-point vectors sampled along the trajectory.  `vgs`/`vds`/`vbs`
#: are the bias the noise deck is rebuilt at; `id`/`gm`/`gds` are what the
#: reproduction check compares, and `gm`/`gds` are also what the extracted
#: `S_id` is sanity-checked against as an effective noise conductance.
OP_VECTORS = ("vgs", "vds", "vbs", "id", "gm", "gds")


def _join_continuations(text: str) -> list[str]:
    """SPICE `+` continuation lines folded into their parent, in order."""
    out: list[str] = []
    for raw in text.splitlines():
        if raw.startswith("+") and out:
            out[-1] = out[-1].rstrip() + " " + raw[1:].strip()
        else:
            out.append(raw)
    return out


def stage_device_lines(src: str) -> dict[str, dict[str, str]]:
    """Every MOS instance of `.subckt vco_stage`, as the committed netlist writes it.

    Returns `{instance: {"d","g","s","b","model","params","line"}}`.  `params` is
    the instance's parameter text verbatim, continuations folded -- the whole
    point being that `noise_deck` re-instantiates the device with the drawn
    geometry rather than a plausible subset of it.

    Raises if `vco_stage`'s device set is not the four this directory knows how
    to bias, because a silent partial match would characterise three devices and
    report them as the ring.
    """
    lines = _join_continuations(src)
    body: list[str] = []
    inside = False
    for ln in lines:
        low = ln.strip().lower()
        if low.startswith(".subckt vco_stage "):
            inside = True
            continue
        if inside and low.startswith(".ends"):
            break
        if inside:
            body.append(ln)
    if not body:
        raise ValueError("design/netlist/vco.spice: no `.subckt vco_stage` body found")

    found: dict[str, dict[str, str]] = {}
    pat = re.compile(
        r"^(X\w+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+([np]fet_03v3)\s+(.*)$",
        re.IGNORECASE,
    )
    for ln in body:
        m = pat.match(ln.strip())
        if not m:
            continue
        found[m.group(1).upper()] = {
            "d": m.group(2),
            "g": m.group(3),
            "s": m.group(4),
            "b": m.group(5),
            "model": m.group(6).lower(),
            "params": m.group(7).strip(),
            "line": ln.strip(),
        }
    if set(found) != set(RING_DEVICES):
        raise ValueError(
            "design/netlist/vco.spice: `vco_stage`'s MOS instance set changed -- "
            f"expected {sorted(RING_DEVICES)}, found {sorted(found)}"
        )
    return found


def device_line(src: str, instance: str, *, name: str = "xm1",
                nodes: tuple[str, str, str, str] = ("d", "g", "0", "b")) -> str:
    """One committed ring device, re-instantiated standalone on `nodes`.

    The model name and the whole parameter text are the committed netlist's, so
    `W`, `L`, `nf`, the `ad`/`as`/`pd`/`ps` area/perimeter expressions, the
    `nrd`/`nrs` terminal-resistance squares and the `sa`/`sb`/`sd` stress
    distances all come across.  Only the four node names change.
    """
    dev = stage_device_lines(src)[instance.upper()]
    d, g, s, b = nodes
    return f"{name} {d} {g} {s} {b} {dev['model']} {dev['params']}"


def channel_polarity(src: str, instance: str) -> float:
    """`+1` for an nfet instance, `-1` for a pfet one.

    ngspice reports a pfet's `@m...[vgs]` / `[vds]` / `[vbs]` / `[id]` in the
    device's OWN polarity -- all positive in normal operation -- so a p-type
    bias triple lifted off the trajectory has to be applied to the standalone
    deck with every terminal negated relative to a grounded source.  Getting
    this backwards does not fail loudly: it biases the device off, `.noise`
    happily reports the subthreshold generators, and the resulting table is
    smooth and wrong.  `sid_extract.reproduction()` is what catches it, by
    demanding the standalone `I_d` match the in-situ one.
    """
    return -1.0 if stage_device_lines(src)[instance.upper()]["model"].startswith("p") else 1.0


def op_vector(copy: int, stage: int, instance: str, param: str) -> str:
    """The ngspice expression for one device operating-point vector in the ISF deck.

    The ISF deck instantiates `x<copy> ... vco_isf`, whose stage instances are
    `XS<stage>` of `vco_stage_isf`, whose MOS instances are the committed
    netlist's `XMPH`/`XMP`/`XMN`/`XMNT` wrapping the PDK subcircuit's own `m0`.
    """
    return f"@m.x{copy}.xs{stage}.{instance.lower()}.m0[{param}]"


def trajectory_vectors(stages=(1,), instances=None, copy: int = 0) -> list[str]:
    """The `save`/`wrdata` column list for the trajectory deck, in a fixed order.

    Order is `(stage, instance, param)` and is part of the contract between this
    module and `sid_extract.read_trajectory()`; the reduction indexes columns by
    position, because `wrdata` writes no header.
    """
    if instances is None:
        instances = tuple(RING_DEVICES)
    return [
        op_vector(copy, s, inst, p)
        for s in stages
        for inst in instances
        for p in OP_VECTORS
    ]


def trajectory_deck(*, repo_root, pdk_models, tstop, tstep, tmax, op,
                    stages=(1,), src=None, wrdata="clk.dat"):
    """The ISF bring-up's reference deck, plus the operating-point columns.

    Returns `(deck_text, column_names)`.  Everything electrical is
    `isf_deck.build_deck`'s: one VCO copy, no injection, the same `.option`s,
    the same symmetry-breaking `.ic`.  This function adds nothing but columns,
    on purpose -- see the module docstring.
    """
    vecs = trajectory_vectors(stages=stages)
    deck = isf_deck.build_deck(
        repo_root=repo_root,
        pdk_models=pdk_models,
        injections=(),
        ncopy=1,
        tstop=tstop,
        tstep=tstep,
        tmax=tmax,
        wrdata=wrdata,
        src=src,
        extra_vectors=vecs,
        **op,
    )
    return deck, vecs


#: Frequency band width, Hz, of every `.noise` call in this directory.
#:
#: ngspice's integrated (`noise2`, `noise4`, ...) plot holds the noise
#: INTEGRATED over the analysis band, so a band of exactly 1 Hz makes the
#: integrated number equal the spectral density -- which is the only reason the
#: single-point densities reported here are comparable with
#: `probe_sid_bias.sp.in`'s.  Writing the upper edge as `f * (1 + eps)` instead
#: of `f + 1` silently widens the band in proportion to `f`, so the "density"
#: grows as `sqrt(f)` and every mechanism appears to rise with frequency
#: together -- including a plain resistor's thermal noise, which cannot.  That
#: is exactly the error `sid_extract.units_anchor()` exists to catch, and it
#: caught it during this bring-up.
NOISE_BANDWIDTH_HZ = 1.0


def noise_deck(*, pdk_models, src, instance, vgs, vds, vbs,
               freqs, temp_c, mos_section="typical", rsense=1.0,
               vg_offset=0.0, vd_offset=0.0, vb_offset=0.0) -> str:
    """One standalone ring device at one bias point, with `.noise` at each `freqs`.

    `vgs`/`vds`/`vbs` are the IN-SITU values as ngspice reports them (device
    polarity), straight off the trajectory; this function applies
    `channel_polarity` itself so a caller cannot forget to.

    THE THREE OFFSETS ARE NOT COSMETIC.  Series resistances sit between this
    deck's ideal sources and the bias ngspice reports: the sense resistor, and the
    device's own `rd`/`rs`.  The committed netlist supplies `nrd`/`nrs`, so BSIM4
    instantiates internal drain and source nodes -- which is also why
    `onoise_total.m.xm1.m0.rd`/`.rs` exist at all -- and `@m...[vgs]`,
    `@m...[vds]` and `@m...[vbs]` are all measured against the INTERNAL source
    node, which sits at `rs * I_d` off the grounded external one.  For this ring's
    `XMN`, `rd + rs` is 1.28 Ohm: enough to shift `V_ds` by ~1e-3 relative at the
    phases where a switching device sits in deep triode (`V_ds` of a couple of
    millivolts), and `V_gs` by 3e-5 relative at the phases where it carries its
    peak current.  Both are the same size as differences this directory reports.

    The offsets are NOT computed as the closed-form `I_d * (rd + rs + rsense)`, and
    the reason is a SIGN that is not constant.  A ring device's `V_ds` crosses zero
    twice per cycle, and BSIM4 handles `V_ds < 0` by swapping source and drain
    internally, so the `I_d` it reports there is positive while the `V_ds` it
    reports is negative: the reported current's sign does not follow `V_ds`.  Add
    the two p-type devices' own polarity flip and there is no fixed sign for the
    correction -- `run.py`'s `checks` stage measures both signs at four phases of
    all four device classes (`bias_correction`), and which sign is the better one
    changes with the device AND with the phase.  Worst residual left by the wrong
    choice: 3.2e-3 relative on `I_d` (`XMN` at its deep-triode phase, `V_ds` = 5.9
    mV), against 1.0e-6 for the right one at the same point; on `XMPH` at its own
    deep-triode phase the ranking is reversed.

    `run.py` instead takes one Newton step on each OBSERVED residual -- run once
    with all three offsets zero, read `@m...[vgs]`/`[vds]`/`[vbs]`, re-run with
    `offset = polarity * (target - observed)`.  That is sign-agnostic, converges in
    one step because the Jacobian is the identity to within
    `(rd + rs + rsense) * g`, and leaves a residual the reduction reports instead
    of assuming: measured at every sampled phase of every corner, `<= 7.2 uV` on
    all three voltages and `<= 8.9e-6` relative on `I_d`, `g_m` and `g_ds`.  That
    last figure is worth naming for a second reason: it settles, by measurement, a
    question this deck would otherwise have to assume away -- ngspice's transient
    `@m...[id]` agreeing with a standalone `op`'s to ~1e-5 means it IS the channel
    current at the sampled timepoints, not channel plus `dQ_d/dt`.

    One `.noise` per frequency in one deck, each in a 1 Hz band, each preceded by
    its own `ac` so the transimpedance is measured at the same frequency rather
    than assumed flat.  `setplot noise<2k+2>` selects the k-th call's INTEGRATED
    plot (ngspice allocates two plots per `noise`: the spectral one then the
    integrated one).
    """
    sign = channel_polarity(src, instance)
    models = Path(pdk_models)
    vg = sign * vgs + vg_offset
    vb = sign * vbs + vb_offset
    vd = sign * vds + vd_offset
    out: list[str] = []
    a = out.append
    a("* gf180-pll :: period-jitter :: S_id along the trajectory -- GENERATED.")
    a("* Generated by sim/period-jitter/sid-trajectory/sid_deck.py; see that")
    a("* directory's README.md for what this deck is and is not evidence for.")
    a(f'.include "{models / "design.ngspice"}"')
    a(f'.lib "{models / "sm141064.ngspice"}" {mos_section}')
    a(f".temp {temp_c:g}")
    a(f"vg g 0 dc {vg:.12e}")
    a(f"vb b 0 dc {vb:.12e}")
    a(f"vd dd 0 dc {vd:.12e}")
    a(f"rs dd d {rsense:.8e}")
    # 1 A AC, drain -> source, for the transimpedance; and, being the `.noise`
    # input source, it also makes `inoise_total` a drain-current density.
    a("iprb 0 d dc 0 ac 1")
    a(device_line(src, instance))
    a(".control")
    a("op")
    a("print " + " ".join(f"@m.xm1.m0[{p}]" for p in OP_VECTORS))
    # The EXTERNAL drain node, for `sid_extract.series_resistance()`: the gap
    # between it and `@m.xm1.m0[vds]` is `(rd + rs + rsense) * I_d`.
    a("print v(d)")
    for k, f in enumerate(freqs):
        a(f"ac lin 1 {f:.12g} {f:.12g}")
        a(f"let zm{k} = mag(v(d))")
        a(f"print zm{k}")
        a(f"noise v(d) iprb lin 2 {f:.12g} {f + NOISE_BANDWIDTH_HZ:.12g} 1")
        a(f"setplot noise{2 * k + 2}")
        a("print onoise_total_rs_thermal")
        a("print onoise_total.m.xm1.m0.id onoise_total.m.xm1.m0.1overf")
        a("print inoise_total.m.xm1.m0.id inoise_total.m.xm1.m0.1overf")
    a(".endc")
    a(".end")
    return "\n".join(out) + "\n"
