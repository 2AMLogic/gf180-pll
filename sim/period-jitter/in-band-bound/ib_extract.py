"""gf180-pll :: period-jitter :: in-band-bound -- the reduction.

Everything that turns ngspice output into the numbers this directory reports,
kept free of any simulator so `sim/tests/test_in_band_bound.py` can pin it.

WHAT IS BOUNDED, AND WHY IT IS A DIFFERENT CALCULATION FROM #520's.
`../random-bound/` (issue #520, DR-032) bounds the random period jitter the
generators inside `vco` and the loop-filter resistor produce.  It states, as a
scope, that it does not inject the charge pump, the PFD, the feedback divider or
the lock detector.  This directory bounds those four (issue #580).  They are
not bounded the same way, because they do not act the same way: none of them
moves the ring's phase directly.  Every one of them acts on the output only by
changing **the charge delivered to the loop filter in one reference cycle**, and
that charge reaches the output phase through the closed loop's low-pass
transfer -- which is what makes the answer small, and what has to be turned from
an argument into an inequality.

THE BOUND, stated before anything is measured.  Six steps, each derived in the
docstring of the function that applies it.

  1. ENUMERATION.  In the committed `design/netlist/pll_top.spice`, the four
     blocks touch the rest of the PLL through exactly four nets: `VCTRL` (the
     charge pump's output current), `UP`/`DN` (the PFD's outputs, which are
     also the lock detector's only inputs, and which gate the charge pump's
     switches), `FB` (the divider's output, which is the PFD's second input),
     and `CLK` (the divider's INPUT, which is also the measured output).  The
     first three act only by changing one reference cycle's charge; `CLK` is
     the one path that does not pass through the loop and is bounded
     separately (`clk_loading_period_variance`).  `connectivity_claim` checks
     the enumeration against the netlist rather than asserting it.
  2. CHARGE -> INPUT-REFERRED PHASE.  The PFD/charge-pump pair delivers
     `I_cp T_ref / 2 pi` coulombs per radian of input phase error, so a charge
     error `dq` in one cycle is indistinguishable from an input phase error
     `dphi = 2 pi dq / (I_cp T_ref)`; a displacement `dt` of a switch edge is
     `dq = I_cp dt`, i.e. `dphi = 2 pi dt / T_ref` with `I_cp` cancelled
     (`charge_to_phase`, `timing_to_phase`).
  3. INPUT PHASE -> OUTPUT PHASE, IN LOCK.  `S_phi_out = N^2 |G(f)|^2 S_phi_in`
     with `G = T/(1 + T)`, taken as the UPPER ENVELOPE over every loop the
     as-built filter admits at the ratified 45 degree phase-margin floor
     (`closed_loop_envelope`, over `../random-bound/rb_extract.admissible_loops`)
     -- so the bound holds whichever legal configuration the part runs in, and
     in particular at the widest loop it admits, which is the worst one here.
  4. OUTPUT PHASE -> PERIOD.  One period is the first difference of output
     phase: `dT/T0 = -(phi(t+T0) - phi(t))/2 pi`, so
     `var(dT/T0) = (1/4 pi^2) int S_phi_out(f) 4 sin^2(pi f T0) df`
     (`period_weight`).  That weight is `~ (2 pi f T0)^2` in band -- 3.4e-3 at
     1.4 MHz against a 150 MHz output -- and it is the whole reason these four
     blocks are small.  It is applied as an integral, not as one number.
  5. SAMPLING.  Every quantity in step 2 is a once-per-reference-cycle
     sequence, so its spectrum lives on `0 .. f_ref/2` and anything the
     underlying continuous-time noise has above `f_ref/2` folds into that band.
     `fold_to_nyquist` splits a measured density there: the in-band part keeps
     its shape, the part above is re-emitted as the flat density an
     independent-per-cycle sequence of the same variance has (`2 sigma^2/f_ref`).
     Total variance is preserved, and no content is dropped.
  6. CYCLOSTATIONARY -> THE WORST INSTANT.  Two places, both one-sided:
     (a) the charge pump conducts only for the reset-window overlap `t_on`, and
     its noise is measured with both switches fully on, which is the largest
     density any instant of that window has (`gated_charge_spectrum`);
     (b) a logic stage's contribution to the timing of its own output edge is
     `v_n/SR`, and `v_n` is bounded by the stage's STATIONARY output-noise
     variance at its trip point, because a CMOS stage's output-noise variance
     is proportional to its small-signal gain and the gain is maximal at the
     trip point (`edge_jitter`).  That is measured here, not asserted: the
     `cells` stage runs `.noise` at several biases across each cell's
     transition and reports the trip point's dominance.

     Both (a) and (b) are the same shape of inequality `../random-bound` uses
     for the ring (replace a time-varying density by its maximum), applied to
     sources whose duty cycle is not 100 %.  For the charge pump that duty cycle
     is the whole point: its generators are live for `t_on ~ ns` out of a 40 ns
     reference period, and `gated_charge_spectrum` is where that enters -- as a
     stated factor, not as an assumption buried in an amplitude.
  7. WHICH STAGES ARE IN A PATH AT ALL.  A gate's noise displaces a
     charge-pump switch edge only if it sits between a triggering input edge and
     that switch edge.  `TIMING_PATHS` declares those gates per path, and
     `timing_path_claim` checks every entry against the committed netlist rather
     than counting devices.  Two of the four blocks are most of the difference:
     the divider chain retimes `FB` on `CLK` through one flip-flop, so its other
     226 MOS devices set no edge time; and the lock detector is in no path at
     all -- its only output leaves `pll_top` unconsumed -- so it acts only by
     loading `UP`/`DN`, which `ib_deck.GATE_LOADS` measures.  The PFD's reset
     path is common mode between `UP` and `DN` and so is scaled by the measured
     up/down current imbalance (`common_mode_scale`).

HOW LOOSE, reported not hidden.  Each stage in a path is charged its own cell's
STATIONARY output noise at its TRIP POINT, into a load capacitance larger than
anything the design presents, divided by the slowest slew that cell shows when
driven by the slowest edge measured anywhere in the three digital blocks.  The
stages in a path are independent generators and add in QUADRATURE; the linear
(perfectly-correlated) figure is reported beside it so the size of that choice
is visible, and so is the figure the retired every-device-in-series count would
have given.
"""

from __future__ import annotations

import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RB = HERE.parent / "random-bound"
# APPENDED, NOT INSERTED AT THE FRONT.  `random-bound` has its own `run.py`; a
# caller that imports this module and then does `import run` (`summarize.py`
# does exactly that) must resolve THIS directory's `run.py`, not that one.
# Every caller inserts its own directory at `sys.path[0]` before importing
# this module, so appending here only adds `rb_extract` as a fallback without
# shadowing a same-named module the caller's own directory already provides.
if str(RB) not in sys.path:
    sys.path.append(str(RB))

import rb_extract  # noqa: E402

K_B = rb_extract.K_B
kelvin = rb_extract.kelvin
log_grid = rb_extract.log_grid
parse_print = rb_extract.parse_print
sigma_upper = rb_extract.sigma_upper


# ---------------------------------------------------------------------------
# step 1: the enumeration
# ---------------------------------------------------------------------------
def _join_continuations(text: str) -> list[str]:
    out: list[str] = []
    for raw in text.splitlines():
        if raw.startswith("+") and out:
            out[-1] = out[-1].rstrip() + " " + raw[1:].strip()
        else:
            out.append(raw)
    return out


def subckt_body(src: str, name: str) -> list[str]:
    """The instance/device lines of `.subckt <name>`, continuations folded."""
    body: list[str] = []
    inside = False
    for ln in _join_continuations(src):
        s = ln.strip()
        low = s.lower()
        if low.startswith(f".subckt {name.lower()} "):
            inside = True
            continue
        if inside and low.startswith(".ends"):
            return body
        if inside and s and not s.startswith("*"):
            body.append(s)
    raise ValueError(f"no `.subckt {name}` in the netlist")


#: `pll_top`'s five instances, by instance name, and the block each one is.
#: Used only to name things; the connectivity claim below is what is checked.
TOP_INSTANCES = {
    "XPFD": "pfd_cp", "XLF": "loop_filter", "XVCO": "vco",
    "XDIV": "divider_chain", "XLD": "lock_detector",
}


def connectivity_claim(src: str) -> dict:
    """Which nets each `pll_top` instance shares with which other instance.

    This is step 1 of the bound, checked against the committed netlist instead
    of asserted.  Returns `{"nets": {net: [instance, ...]}, "shared":
    {(a, b): [net, ...]}}` over `pll_top`'s own instance lines, so a
    re-netlisted `pll_top` that gave the lock detector a second consumer, or
    the divider a second connection to the analog side, would change this
    dict and fail `sim/tests/test_in_band_bound.py`.
    """
    body = subckt_body(src, "pll_top")
    nets: dict[str, list[str]] = {}
    seen: dict[str, str] = {}
    for ln in body:
        tok = ln.split()
        inst = tok[0].upper()
        if inst not in TOP_INSTANCES:
            raise ValueError(f"pll_top: unexpected instance {inst}")
        if TOP_INSTANCES[inst] != tok[-1].lower():
            raise ValueError(f"pll_top: {inst} is no longer a {TOP_INSTANCES[inst]}")
        seen[inst] = tok[-1].lower()
        for net in tok[1:-1]:
            nets.setdefault(net.upper(), []).append(inst)
    if set(seen) != set(TOP_INSTANCES):
        raise ValueError(f"pll_top: instances changed -- found {sorted(seen)}")
    shared: dict[tuple[str, str], list[str]] = {}
    for net, insts in nets.items():
        uniq = sorted(set(insts))
        for i, a in enumerate(uniq):
            for b in uniq[i + 1:]:
                shared.setdefault((a, b), []).append(net)
    return {"nets": {k: sorted(set(v)) for k, v in nets.items()},
            "shared": {k: sorted(v) for k, v in shared.items()}}


#: The nets the four in-band blocks may reach the output through, and the
#: mechanism each one is bounded by.  `connectivity_claim` must show no
#: instance-to-instance net outside this map plus the supplies/configuration.
IN_BAND_PATHS = {
    "VCTRL": "charge delivered to the loop filter (charge pump current noise)",
    "UP": "charge-pump switch timing (PFD, lock-detector loading)",
    "DN": "charge-pump switch timing (PFD, lock-detector loading)",
    "FB": "PFD second-edge timing (divider chain)",
    "CLK": "the measured output node itself (divider input loading) -- NOT through the loop",
}

#: Nets `pll_top` shares between instances that carry no in-band noise path:
#: the supplies and the static configuration codes.  Named so that a new
#: shared net shows up as an unclassified one rather than being absorbed.
INERT_SHARED_NETS = frozenset({"VDD", "VSS", "VDD_VCO", "GND_VCO", "VDD_DIV"})


def unclassified_shared_nets(src: str) -> list[str]:
    """Nets shared between two `pll_top` instances that step 1 does not cover."""
    claim = connectivity_claim(src)
    out = []
    for net, insts in claim["nets"].items():
        if len(set(insts)) < 2:
            continue
        if net in IN_BAND_PATHS or net in INERT_SHARED_NETS:
            continue
        out.append(net)
    return sorted(out)


# ---------------------------------------------------------------------------
# step 1b: which stages are in a timing path, and which are not
# ---------------------------------------------------------------------------
#: Every single-stage gate whose own noise displaces a charge-pump switch edge,
#: grouped by the path it sits in, declared relative to `.subckt pll_top` and
#: checked against the committed netlist by `timing_path_claim`.
#:
#: WHY A DECLARED PATH AND NOT A DEVICE COUNT.  A block's noise reaches the
#: output by displacing the edge that opens or closes a charge-pump switch.  A
#: gate whose output is not between a triggering input edge and that switch edge
#: does not displace it -- it is not in the path, and charging the block for it
#: is not conservatism, it is a different circuit.  Two places where that
#: distinction is worth an order of magnitude or more:
#:
#:  * THE DIVIDER CHAIN retimes its output on `CLK`: `XFRT` is a `dff_tg_3v3`
#:    with `D = DIVOUT`, `CK = CLK`, `Q = FB`.  So `FB`'s edge sits where `CLK`'s
#:    edge plus that one flip-flop's clock-to-Q delay puts it, and the chain's
#:    226 other MOS devices -- the six `div23_cell`s, the mode logic, the
#:    NAND/NOR decode -- decide only WHETHER `FB` toggles on a given `CLK` edge,
#:    never when.  Their noise changes no edge time to first order.  (The
#:    assumption that makes this true is that `DIVOUT` settles before the `CLK`
#:    edge that samples it -- a setup-time statement, not a noise one, and the
#:    deterministic campaign's own divider timing is where it is established.)
#:  * THE LOCK DETECTOR is in no path at all.  Its only inputs are `UP`/`DN` and
#:    its only output `LOCK` reaches no other `pll_top` instance
#:    (`connectivity_claim` is what establishes that, per point, from the
#:    netlist).  It can act on the output solely by loading `UP`/`DN`, which is
#:    `ib_deck.GATE_LOADS["up"]`'s measurement and not a stage count.
#:
#: The reset path is split from the rest because it is COMMON MODE: `RB` resets
#: both latches, so a displacement of `RB` lengthens the `UP` and the `DN` pulse
#: by the same amount, and the NET charge into the filter -- `I_up t_up - I_dn
#: t_dn` -- changes only through the up/down current IMBALANCE.  The two stages
#: inside each latch are not common mode (each belongs to one output), so they
#: are listed per side and charged in full.  `xlat_*.xn1` appears in both its
#: side's rising path and its falling path; counting it twice is the
#: conservative reading of a gate whose noise acts on both edges.
TIMING_PATHS = {
    # REF's rising edge to UP's rising edge.  In `edgedet` the rising edge
    # reaches `PULSE` through `xnd` (whose `X` input is the edge itself) and
    # `xi6`; the five-inverter chain `xi1..xi5` sets how long the pulse LASTS,
    # which decides nothing about when the latch is set.
    "pfd_ref_to_up": [
        ("xpfd.xpfd.xed_ref.xnd", "pfdcp_nand2_3v3"),
        ("xpfd.xpfd.xed_ref.xi6", "pfdcp_inv_3v3"),
        ("xpfd.xpfd.xinv_sr", "pfdcp_inv_3v3"),
        ("xpfd.xpfd.xlat_ref.xn1", "pfdcp_nand2_3v3"),
    ],
    # FB's rising edge to DN's rising edge -- the same four stages on the
    # feedback side.  A displacement of FB is indistinguishable from the
    # opposite displacement of REF, which is why the divider's own path below
    # ends here.
    "pfd_fb_to_dn": [
        ("xpfd.xpfd.xed_fb.xnd", "pfdcp_nand2_3v3"),
        ("xpfd.xpfd.xed_fb.xi6", "pfdcp_inv_3v3"),
        ("xpfd.xpfd.xinv_sf", "pfdcp_inv_3v3"),
        ("xpfd.xpfd.xlat_fb.xn1", "pfdcp_nand2_3v3"),
    ],
    # CLK's rising edge to FB's, through the retiming flip-flop only: the two
    # clock inverters, the slave pass gate the second one opens, and the
    # inverter that drives Q.
    "divider_retime": [
        ("xdiv.xfrt.xickb", "inv_3v3"),
        ("xdiv.xfrt.xickbb", "inv_3v3"),
        ("xdiv.xfrt.xtgsi", "tgate_3v3"),
        ("xdiv.xfrt.xic", "inv_3v3"),
    ],
    # UP to the up switch's gate.  DN drives `XMSWDN`'s gate directly, so the
    # down side has no driver stage; the `B0`/`B1` inverters are static trim.
    "cp_switch_driver": [
        ("xpfd.xcp.xi_up", "pfdcp_inv_3v3"),
    ],
    # The falling edges of UP and DN, up to and including the reset inverter:
    # common to both, so scaled by the up/down current imbalance.
    "pfd_reset_common": [
        ("xpfd.xpfd.xnand_rst", "pfdcp_nand2_3v3"),
        ("xpfd.xpfd.xinv_r0", "pfdcp_inv_3v3"),
        *((f"xpfd.xpfd.xd{k}", "pfdcp_inv_3v3") for k in range(1, 25)),
        ("xpfd.xpfd.xinv_rb", "pfdcp_inv_3v3"),
    ],
    # Inside each latch, RB to that latch's own output -- one output each, so
    # not common mode.
    "pfd_reset_up_side": [
        ("xpfd.xpfd.xlat_ref.xn2", "pfdcp_nand2_3v3"),
        ("xpfd.xpfd.xlat_ref.xn1", "pfdcp_nand2_3v3"),
    ],
    "pfd_reset_dn_side": [
        ("xpfd.xpfd.xlat_fb.xn2", "pfdcp_nand2_3v3"),
        ("xpfd.xpfd.xlat_fb.xn1", "pfdcp_nand2_3v3"),
    ],
}

#: The one path whose noise is common mode between UP and DN, and so is scaled
#: by the up/down current imbalance rather than counted in full.
COMMON_MODE_PATH = "pfd_reset_common"

#: Which of the four blocks owns each path, for reporting against the issue's
#: per-block acceptance criterion.
PATH_BLOCK = {
    "pfd_ref_to_up": "pfd", "pfd_fb_to_dn": "pfd",
    "pfd_reset_common": "pfd", "pfd_reset_up_side": "pfd",
    "pfd_reset_dn_side": "pfd",
    "divider_retime": "divider_chain",
    "cp_switch_driver": "charge_pump",
}


def resolve_instance(src: str, top: str, dotted: str) -> str:
    """The model name of `dotted` (e.g. `xpfd.xpfd.xd7`) inside `.subckt top`.

    Raises if any level of the path is not an instance of the level above, so a
    `TIMING_PATHS` entry can never name a gate this netlist does not contain in
    that position.
    """
    here = top
    for step in dotted.split("."):
        found = None
        for ln in subckt_body(src, here):
            tok = ln.split()
            if tok[0].lower() != step.lower():
                continue
            for i in range(1, len(tok)):
                if i == len(tok) - 1 or "=" in tok[i + 1]:
                    found = tok[i].lower()
                    break
            break
        if found is None:
            raise ValueError(f"{top}: no instance `{step}` in `{here}` (path {dotted})")
        here = found
    return here


def timing_path_claim(src: str) -> dict:
    """Check every `TIMING_PATHS` entry against the committed netlist.

    Returns `{path: [(instance, cell), ...]}` with the cell each instance
    ACTUALLY is; raises if a declared instance is missing or is a different cell
    than declared.  This is what keeps the stage counting honest across a
    re-netlist: a renamed or retyped gate fails here rather than quietly
    dropping out of, or into, a path.
    """
    out: dict[str, list] = {}
    for name, stages in TIMING_PATHS.items():
        got = []
        for inst, cell in stages:
            actual = resolve_instance(src, "pll_top", inst)
            if actual != cell.lower():
                raise ValueError(
                    f"{name}: `{inst}` is a `{actual}`, declared `{cell}`")
            got.append((inst, actual))
        out[name] = got
    return out


# ---------------------------------------------------------------------------
# step 2: charge and timing, referred to the PFD's input
# ---------------------------------------------------------------------------
def charge_to_phase(icp_a: float, t_ref_s: float) -> float:
    """`dphi/dq`, rad/C: the inverse of the PFD/charge-pump gain.

    In lock the pair delivers current `I_cp` for `phi_e T_ref / 2 pi` seconds
    per reference cycle, i.e. `K_pd = I_cp T_ref / 2 pi` coulombs per radian.
    A charge error `dq` on the loop filter is therefore indistinguishable from
    an input phase error `dphi = dq / K_pd`.  `I_cp` here is the current the
    conducting leg actually carries at this PVT point, measured, not the
    nominal trim value.
    """
    if icp_a <= 0 or t_ref_s <= 0:
        raise ValueError("I_cp and T_ref must be positive")
    return 2.0 * math.pi / (icp_a * t_ref_s)


def timing_to_phase(t_ref_s: float) -> float:
    """`dphi/dt`, rad/s, for a displacement of a charge-pump switch edge.

    `dq = I_cp dt` through `charge_to_phase` gives `2 pi / T_ref` -- `I_cp`
    cancels.  So the PFD's, the divider's and the lock detector's
    contributions do not depend on the charge-pump trim code at all: a timing
    error at the PFD is a phase error, full stop.  That is why this directory
    measures those three in seconds and the charge pump in coulombs.
    """
    if t_ref_s <= 0:
        raise ValueError("T_ref must be positive")
    return 2.0 * math.pi / t_ref_s


# ---------------------------------------------------------------------------
# step 3: the closed loop
# ---------------------------------------------------------------------------
def closed_loop_sq(f: float, loop: dict) -> float:
    """`|T(j2pi f)/(1 + T(j2pi f))|^2` for one loop.

    The transfer from an input phase error to the output phase, divided by `N`.
    Complementary to `../random-bound/rb_extract.error_transfer_sq`, which is
    `|1/(1+T)|^2` -- that one is what the VCO's own noise sees, this one is
    what a source at the PFD's input sees, and the two are what makes the same
    loop suppress one and pass the other.
    """
    w = 2 * math.pi * f
    t = loop["A"] * rb_extract._z(w, loop["r"], loop["c1"], loop["c2"]) / (1j * w)
    return abs(t / (1.0 + t)) ** 2


def closed_loop_envelope(freqs, loops) -> list[float]:
    """Upper envelope of `|T/(1+T)|^2` over `loops`, on `freqs`.

    The envelope, not one loop: `admissible_loops` enumerates every `(R, C1,
    C2, A)` the as-built filter admits at `PM >= 45` degrees, which is a
    SUPERSET of what the trim rule selects, so a bound computed from the
    envelope holds for whatever the rule actually picks.  For an in-band
    source the widest admissible loop is the worst one (more of its noise
    reaches the output, and at a higher frequency, where the period weight is
    larger), so the envelope is conservative in the direction that matters.
    """
    return [max(closed_loop_sq(f, lp) for lp in loops) for f in freqs]


# ---------------------------------------------------------------------------
# step 4: phase to period
# ---------------------------------------------------------------------------
def period_weight(f: float, f0: float) -> float:
    """`4 sin^2(pi f / f0)`: one period is the first difference of phase.

    The k-th rising edge of the output sits where `2 pi f0 t + phi(t) = 2 pi k`,
    so `T_k = T0 - (phi(t_{k+1}) - phi(t_k))/(2 pi f0)` and
    `dT_k/T0 = -(phi(t+T0) - phi(t))/(2 pi)`.  Differencing multiplies a
    spectral component by `|1 - e^{-j 2 pi f T0}|^2 = 4 sin^2(pi f T0)`.  In
    band this is `(2 pi f T0)^2` -- 3.4e-3 at 1.4 MHz against 150 MHz -- and
    it is why the four in-band blocks are small.  It is NOT approximated by
    that limit anywhere in this directory; the exact weight is integrated.
    """
    return 4.0 * math.sin(math.pi * f / f0) ** 2


def period_variance(freqs, s_phi_in, env_cl, *, f0_hz: float, n_div: float) -> float:
    """`var(dT/T0)` from an input-referred phase density, closed loop.

    `(1/4 pi^2) int N^2 |G|^2 S_phi_in(f) 4 sin^2(pi f/f0) df`, trapezoid in
    `ln f` (`freqs` is log-spaced and `s_phi_in`/`env_cl` are on it).  The
    integral is taken over the grid as given: the caller's grid runs to
    `f_ref/2`, above which a once-per-cycle sequence has no content (step 5).
    """
    if not (len(freqs) == len(s_phi_in) == len(env_cl)):
        raise ValueError("freqs, density and envelope must be the same length")
    if len(freqs) < 2:
        raise ValueError("need at least two frequencies to integrate")
    acc = 0.0
    prev = None
    for f, s, e in zip(freqs, s_phi_in, env_cl):
        if f <= 0:
            raise ValueError("frequencies must be positive")
        cur = (math.log(f), f * s * e * period_weight(f, f0_hz))
        if prev is not None:
            acc += 0.5 * (cur[0] - prev[0]) * (cur[1] + prev[1])
        prev = cur
    return n_div ** 2 * acc / (4.0 * math.pi ** 2)


# ---------------------------------------------------------------------------
# step 5: the once-per-cycle sampling
# ---------------------------------------------------------------------------
def integrate_log(freqs, dens) -> float:
    """`int dens df` by trapezoid in `ln f` over a log-spaced grid."""
    acc = 0.0
    prev = None
    for f, s in zip(freqs, dens):
        cur = (math.log(f), f * s)
        if prev is not None:
            acc += 0.5 * (cur[0] - prev[0]) * (cur[1] + prev[1])
        prev = cur
    return acc


def high_frequency_tail(freqs, dens) -> float:
    """`int_{f_hi}^inf dens df` assuming the measured `1/f^2` roll-off continues.

    A single-pole node's density falls as `f^-2` past its corner, so the
    omitted tail is `S(f_hi) f_hi / (p - 1)` with `p` the slope MEASURED from
    the grid's last two points, floored at 2 (a slower roll-off than the last
    decade shows would be a measurement that has not reached the corner, and
    the caller's grid is checked for that).  Added rather than dropped: it is
    part of the variance an edge samples.
    """
    if len(freqs) < 2:
        raise ValueError("need two points to measure a slope")
    f1, f2 = freqs[-2], freqs[-1]
    s1, s2 = dens[-2], dens[-1]
    if s2 <= 0 or s1 <= 0:
        return 0.0
    p = -math.log(s2 / s1) / math.log(f2 / f1)
    if p <= 1.0:
        raise ValueError(
            f"the density's top-decade slope is f^-{p:.2f}, which does not "
            "integrate -- the measurement grid has not reached the node's corner"
        )
    return s2 * f2 / (p - 1.0)


def _split_at(freqs, weighted, fn: float):
    """Split a log grid at `fn`, with the STRADDLING interval in both halves.

    `fn` almost never falls on a grid point, and taking `f <= fn` for the low
    half and `f >= fn` for the high half leaves the one interval that straddles
    `fn` in NEITHER -- a sliver of variance silently dropped, which is the wrong
    direction for a bound.  So the low half is extended up to the first point
    above `fn` and the high half down to the last point below it: the straddling
    interval is counted TWICE, which over-states the total by at most that one
    interval's contribution and never understates it.
    """
    lo_i = [i for i, f in enumerate(freqs) if f <= fn]
    hi_i = [i for i, f in enumerate(freqs) if f >= fn]
    if lo_i and lo_i[-1] + 1 < len(freqs):
        lo_i.append(lo_i[-1] + 1)
    if hi_i and hi_i[0] > 0:
        hi_i.insert(0, hi_i[0] - 1)
    return ([freqs[i] for i in lo_i], [weighted[i] for i in lo_i],
            [freqs[i] for i in hi_i], [weighted[i] for i in hi_i])


def fold_to_nyquist(freqs, dens, f_ref: float):
    """Split a continuous-time density at `f_ref/2` for a once-per-cycle sample.

    Returns `(in_band_freqs, in_band_dens, flat_dens, above_var)`.  A sequence
    sampled once per reference cycle has its spectrum on `0 .. f_ref/2`; the
    underlying process's content ABOVE `f_ref/2` aliases into that band, and
    the aliased part of a broadband process is, cycle to cycle, independent to
    the accuracy anything here needs -- an independent sequence of variance
    `sigma^2` has the flat one-sided density `2 sigma^2 / f_ref`.  So:

      * `f < f_ref/2`: the measured density, unchanged -- a slow (flicker)
        component tracks from one cycle to the next and must keep its shape,
        because the period weight of step 4 is what makes it harmless and that
        weight is frequency-dependent;
      * `f > f_ref/2`: integrated (plus `high_frequency_tail`) and re-emitted
        flat.

    Total variance is preserved, to the one straddling interval `_split_at`
    counts twice rather than drop.  Nothing is dropped, and no content is moved
    DOWN in frequency except by the aliasing that physically happens.
    """
    fn = f_ref / 2.0
    lo_f, lo_s, hi_f, hi_s = _split_at(freqs, list(dens), fn)
    if len(lo_f) < 2:
        raise ValueError("the grid must resolve the band below f_ref/2")
    if len(hi_f) < 2:
        raise ValueError("the grid must reach past f_ref/2")
    above = integrate_log(hi_f, hi_s) + high_frequency_tail(freqs, dens)
    return lo_f, lo_s, 2.0 * above / f_ref, above


# ---------------------------------------------------------------------------
# step 6a: the charge pump's pulsed duty cycle
# ---------------------------------------------------------------------------
def sinc2(x: float) -> float:
    if x == 0:
        return 1.0
    y = math.pi * x
    return (math.sin(y) / y) ** 2


def gated_charge_spectrum(freqs, s_i, *, t_on: float, f_ref: float):
    """The charge pump's per-cycle charge-error density, from its ON-state current noise.

    THE ADAPTATION THE PULSED DUTY CYCLE NEEDS, stated rather than assumed
    away.  `../random-bound` injects generators that are live every instant of
    every cycle.  The charge pump's are not: both switches conduct only for
    the reset-window overlap `t_on` (measured, 1-3 ns out of a 40 ns reference
    period), and outside it the legs are steered to the dump node and the
    output sees only the off-switch leakage.  So its generators cannot be
    given a stationary density; what one reference cycle sees is

        dq_k = int_{window k} i_n(t) dt,

    a WINDOWED integral of the on-state noise.  For a density `S_i` the window
    contributes `|W(f)|^2 = t_on^2 sinc^2(f t_on)`, so

        var(dq) = int_0^inf S_i(f) t_on^2 sinc^2(f t_on) df,

    which for white `S_i` is exactly `S_i t_on / 2` -- the duty-cycle factor
    `t_on f_ref` below what a continuously-on source of the same density would
    deliver, and the sentence a bound may use only if it states it.  The
    result is split at `f_ref/2` by `fold_to_nyquist`'s rule, so a flicker
    component keeps its in-band shape (it is the same slow drift from cycle to
    cycle) and everything above folds in flat.

    Two one-sided choices: `S_i` is measured with both switches FULLY on,
    which is at least the density at any instant of a window whose edges have
    partially-on switches; and `sinc^2 <= 1` is used only in the direction
    that keeps the folded part whole.  Returns
    `(in_band_freqs, in_band_S_q, flat_S_q, var_above)` in C^2/Hz.
    """
    if t_on <= 0:
        raise ValueError("the overlap window must be positive")
    weighted = [s * t_on ** 2 * sinc2(f * t_on) for f, s in zip(freqs, s_i)]
    fn = f_ref / 2.0
    lo_f, lo_s, hi_f, hi_s = _split_at(freqs, weighted, fn)
    if len(lo_f) < 2 or len(hi_f) < 2:
        raise ValueError("the grid must straddle f_ref/2 with at least two points each side")
    # Past 1/t_on the sinc window falls as f^-2, so the tail integrates; the
    # measured grid is required to reach past 1/t_on for that to be what it is.
    if freqs[-1] < 10.0 / t_on:
        raise ValueError("the noise grid must reach 10/t_on for the window tail to be resolved")
    above = integrate_log(hi_f, hi_s)
    return lo_f, lo_s, 2.0 * above / f_ref, above


# ---------------------------------------------------------------------------
# step 6b: a logic stage's edge
# ---------------------------------------------------------------------------
def edge_jitter(sigma_v: float, slew_v_per_s: float) -> float:
    """`sigma_t = sigma_v / SR`: a noise voltage becomes a timing error.

    A stage's output crosses the next stage's threshold at the instant its
    noiseless waveform would, displaced by `-v_n/SR` for the noise voltage
    `v_n` present at that instant -- exact to first order in `v_n`, and `v_n`
    here is microvolts against volt-scale swings.

    `sigma_v` is the stage's STATIONARY output-noise standard deviation at its
    TRIP POINT.  That bounds the noise actually present at the crossing, for
    two reasons that cover both regimes: if the node's time constant `tau =
    r_o C` is longer than the transition, the noise has had less than `tau` to
    accumulate and so is below the stationary value; if it is shorter, the
    noise is stationary at the instantaneous bias, and the stationary variance
    of a CMOS stage is `~ kT A_v / C` with `A_v` the small-signal gain, which
    is maximal at the trip point.  The `cells` stage measures that maximum
    rather than assuming it, by running `.noise` at several biases across each
    cell's transition and reporting where the maximum falls.

    `SR` is the slowest slew the cell shows when driven by the slowest input
    edge measured anywhere in the three digital blocks.
    """
    if slew_v_per_s <= 0:
        raise ValueError("the slew rate must be positive")
    return sigma_v / slew_v_per_s


#: Floor on the up/down current-imbalance fraction the common-mode reset path is
#: scaled by.  The measured imbalance at a given corner is a SYSTEMATIC figure at
#: nominal device sizes; random mismatch between the up and down legs moves it,
#: and that mismatch is DR-018's quantity, not this campaign's.  So the scale
#: used is the larger of the measured imbalance and this floor, which is far
#: above any plausible mismatch on a 6 um / 0.3 um switch pair and its cascoded
#: leg, and the measured value is recorded beside it.
COMMON_MODE_IMBALANCE_FLOOR = 0.10


def common_mode_scale(i_up: float, i_dn: float,
                      floor: float = COMMON_MODE_IMBALANCE_FLOOR) -> dict:
    """How much of a common-mode edge displacement survives as a charge error.

    `RB` resets both latches, so a displacement `dt` of the reset edge lengthens
    the `UP` and the `DN` pulse by the same `dt`.  The charge the filter receives
    in that cycle changes by `(I_up - I_dn) dt`, not by `I_cp dt`: the net is
    what the loop integrates, and a common-mode widening of both pulses delivers
    only the leg imbalance.  So the reset path's timing noise is referred to the
    PFD's input through the same `timing_to_phase` as any other stage, times

        s = max(|I_up - I_dn| / min(I_up, I_dn), floor),

    with `I_up`, `I_dn` the two legs' MEASURED currents at this PVT point and in
    the conducting state (`cp` stage), and `floor` covering the random mismatch
    those measured currents do not contain.  Returns the scale and both inputs,
    so the result records which of the two set it.
    """
    if i_up <= 0 or i_dn <= 0:
        raise ValueError("both charge-pump legs must carry current")
    measured = abs(i_up - i_dn) / min(i_up, i_dn)
    return {"i_up_A": i_up, "i_dn_A": i_dn, "measured_imbalance": measured,
            "floor": floor, "scale": max(measured, floor),
            "set_by": "measured" if measured > floor else "floor"}


def stage_timing_spectrum(freqs, s_v, *, slew: float, f_ref: float):
    """A stage's output-noise density -> its edge's timing-error density.

    `S_dt(f) = S_v(f)/SR^2`, then `fold_to_nyquist`: the edge samples the
    node's noise once per reference cycle, so the part of `S_v` above
    `f_ref/2` folds in as an independent-per-cycle term and the part below
    keeps its shape.  Returns `(in_band_freqs, in_band_S_dt, flat_S_dt,
    var_above)` in s^2/Hz and s^2.
    """
    scaled = [s / slew ** 2 for s in s_v]
    return fold_to_nyquist(freqs, scaled, f_ref)


# ---------------------------------------------------------------------------
# the assembled per-block term
# ---------------------------------------------------------------------------
def block_period_variance(*, in_band_freqs, in_band_s_dt, flat_s_dt,
                          env_in_band, env_flat_freqs, env_flat,
                          f0_hz: float, f_ref: float, n_div: float,
                          t_ref_s: float) -> dict:
    """One block's `var(dT/T0)`, from its timing-error density.

    The in-band part is integrated on its own grid; the flat (folded) part is
    integrated on the envelope's grid over `0 .. f_ref/2`.  Both go through
    `timing_to_phase` and `period_variance`, so both carry the same `N`, the
    same closed-loop envelope and the same period weight.
    """
    k = timing_to_phase(t_ref_s) ** 2
    v_band = period_variance(in_band_freqs, [s * k for s in in_band_s_dt],
                             env_in_band, f0_hz=f0_hz, n_div=n_div)
    v_flat = period_variance(env_flat_freqs, [flat_s_dt * k] * len(env_flat_freqs),
                             env_flat, f0_hz=f0_hz, n_div=n_div)
    return {"in_band": v_band, "folded": v_flat, "total": v_band + v_flat}


def clk_loading_period_variance(*, sigma_v: float, slew: float, f0_hz: float) -> dict:
    """The one path that does not go through the loop: the divider's `CLK` load.

    `CLK` is the divider chain's input and, at the same time, the node this
    specification's period jitter is measured at.  The divider's input devices
    therefore put noise straight onto the measured edge, with no loop and no
    `4 sin^2` suppression: an edge timing error `sigma_t = sigma_v/SR`, and a
    period is the difference of two successive edges, so
    `var(dT/T0) = 2 sigma_t^2 / T0^2` for independent edge errors (successive
    150 MHz edges are 6.7 ns apart, past the node's own time constant; a
    correlated pair would give LESS, so 2x is the bound).

    `sigma_v` is the part of the noise on `CLK` that the DIVIDER's devices
    produce, with the VCO's output buffer driving that node -- ngspice's
    per-device breakdown separates it from the buffer's own, which `../random-bound`
    already injects and this directory must not count twice.
    """
    sigma_t = edge_jitter(sigma_v, slew)
    var = 2.0 * (sigma_t * f0_hz) ** 2
    return {"sigma_t_s": sigma_t, "var": var, "pct": 100.0 * math.sqrt(var)}


def assemble_bound(terms: dict, *, vco_bound_pct: float, budget_pct: float) -> dict:
    """The in-band bound at one PVT point, in % of the period, against the margin.

    `terms` maps a block name to its `var(dT/T0)`.  They are independent
    sources and add in quadrature.  The comparison is NOT against the full
    `budget_pct`: `../random-bound`'s bound (`vco_bound_pct`, the VCO, bias
    generator and loop-filter resistor at this same point) is already spent,
    so what this directory has to fit inside is

        remaining = sqrt(budget^2 - vco^2)

    which is what `spec/pll.md` leaves once DR-032's term is taken out -- and
    the two add in quadrature because their sources are independent.  `headroom`
    is `remaining / in_band`, the factor this bound clears its own share by;
    `combined_pct` is the whole random half, both directories together, which
    is the number the row must satisfy.
    """
    total = sum(terms.values())
    in_band_pct = 100.0 * math.sqrt(total)
    if not 0.0 <= vco_bound_pct < budget_pct:
        raise ValueError("the VCO-side bound must be inside the budget to leave a margin")
    remaining = math.sqrt(budget_pct ** 2 - vco_bound_pct ** 2)
    combined = math.sqrt(vco_bound_pct ** 2 + in_band_pct ** 2)
    return {
        "terms_pct": {k: 100.0 * math.sqrt(v) for k, v in terms.items()},
        "in_band_pct": in_band_pct,
        "vco_bound_pct": vco_bound_pct,
        "remaining_pct": remaining,
        "headroom": remaining / in_band_pct if in_band_pct > 0 else float("inf"),
        "combined_pct": combined,
        "budget_pct": budget_pct,
        "clears": combined < budget_pct,
    }


# ---------------------------------------------------------------------------
# the noise logs
# ---------------------------------------------------------------------------
def parse_noise_log(text: str, *, groups: dict, anchors: dict, freqs) -> dict:
    """One `.noise`-per-frequency log -> per-group output density, by frequency.

    `groups` maps a group name to the list of device paths whose contributions
    belong to it (ngspice prints `onoise_total.m.<path>.m0`, in V/sqrt(Hz) over
    the 1 Hz analysis band, per device and uncorrelated between devices, so a
    group's density is the sum of its members' SQUARES).  `anchors` maps a
    resistor's vector-name suffix to its `(resistance, temperature)` so the
    units of every call can be checked against `4 k T R` -- the same absolute
    check `../random-bound` and `../sid-trajectory` apply.  The ratio is returned
    per call (`anchor_ratios`, in call order) as well as as a range, because an
    anchor only reads 1 where its own transfer to the output node is 1: on a deck
    whose output node rolls off within the grid (the `CLK` load), the anchor is
    the units check at the bottom of the grid and a measurement of that roll-off
    above it.  A deck with no anchor at all is refused rather than left silently
    unchecked.

    Positional parsing per frequency block (ngspice reprints the same vector
    names once per call), and every named vector must appear: an ngspice
    `print` of an unknown vector prints no `name = value` line at all, so a
    silently short parse is how a renamed net would become a table of zeros.
    """
    seen = parse_print(text)
    names = [n for n, _ in seen]
    vals = [v for _, v in seen]
    cursor = 0

    def take(name):
        nonlocal cursor
        try:
            cursor = names.index(name, cursor)
        except ValueError as exc:
            raise ValueError(
                f"noise log: `{name}` missing after position {cursor}") from exc
        v = vals[cursor]
        cursor += 1
        return v

    per_group: dict[str, list[dict]] = {g: [] for g in groups}
    anchor_err: list[float] = []
    for f in freqs:
        block: dict[str, float] = {}
        for g, paths in groups.items():
            tot = 0.0
            fl = 0.0
            for p in paths:
                tot += take(f"onoise_total.m.{p}.m0") ** 2
                fl += take(f"onoise_total.m.{p}.m0.1overf") ** 2
            block[g] = tot
            per_group[g].append({"freq_Hz": f, "total": tot, "flicker": fl,
                                 "white": max(tot - fl, 0.0)})
        for nm, (r, temp_c) in anchors.items():
            got = take(f"onoise_total_{nm}_thermal")
            want = math.sqrt(4.0 * K_B * kelvin(temp_c) * r)
            anchor_err.append(got / want)
    if not anchor_err:
        raise ValueError("every noise deck in this directory must carry a units anchor")
    return {"per_group": per_group, "anchor_ratios": anchor_err,
            "anchor_ratio_first": anchor_err[0],
            "anchor_ratio_min": min(anchor_err), "anchor_ratio_max": max(anchor_err)}


# ---------------------------------------------------------------------------
# waveform reductions
# ---------------------------------------------------------------------------
read_wrdata = rb_extract.read_wrdata
rising_crossings = rb_extract.rising_crossings


def crossings_with_slew(t, v, level: float):
    """Rising crossings of `level`, each with the chord slew rate there.

    The crossing is placed on the chord between the two stored timepoints that
    straddle it -- `../random-bound/rb_extract.rising_crossings`' construction --
    and the chord's own slope is the slew rate reported for it.  A chord
    UNDER-estimates the instantaneous slope of a convex edge, which makes
    `1/SR` an over-estimate, the safe direction for `edge_jitter`.
    """
    out = []
    for i in range(1, len(t)):
        a, b = v[i - 1], v[i]
        if a < level <= b and t[i] > t[i - 1]:
            sr = (b - a) / (t[i] - t[i - 1])
            out.append({"t": t[i - 1] + (level - a) * (t[i] - t[i - 1]) / (b - a),
                        "slew": sr})
    return out


def falling_crossings_with_slew(t, v, level: float):
    out = []
    for i in range(1, len(t)):
        a, b = v[i - 1], v[i]
        if a >= level > b and t[i] > t[i - 1]:
            sr = (a - b) / (t[i] - t[i - 1])
            out.append({"t": t[i - 1] + (a - level) * (t[i] - t[i - 1]) / (a - b),
                        "slew": sr})
    return out


def pulse_widths(t, v, level: float):
    """Widths of the high pulses of `v` about `level`, in order.

    Each width pairs a rising crossing with the next falling one.  The charge
    pump's overlap window is the shorter of the UP and DN widths and its
    noise-active window is the LONGER -- `gated_charge_spectrum` is given the
    longer, because outside the overlap one leg is still conducting into the
    output and its noise is then uncancelled.
    """
    ups = [c["t"] for c in crossings_with_slew(t, v, level)]
    downs = [c["t"] for c in falling_crossings_with_slew(t, v, level)]
    out = []
    for a in ups:
        nxt = [d for d in downs if d > a]
        if nxt:
            out.append(nxt[0] - a)
    return out


_NUM = r"[-+0-9.eEdD]+"


def parse_op_currents(text: str, pattern: str) -> dict:
    """`@m.<path>.m0[id] = <value>` lines whose path matches `pattern`."""
    out = {}
    for name, val in parse_print(text):
        m = re.match(rf"^@m\.({pattern})\.m0\[id\]$", name)
        if m:
            out[m.group(1)] = val
    return out
