"""Flat LVS reference for the assembled ``pll_top`` (issues #237, #149).

Every block in this repo proved its layout with the foundry LVS deck against
a *flat* reference netlist, because the deck (``align``) does not flatten a
hierarchical schematic to match a flat GDS on its own -- see
``layout/harness/spice_flatten.py``'s module docstring for that failure mode,
hit directly during ``divider_chain``'s bring-up (issue #310). The assembled
``pll_top.gds`` is one flat top cell over five flat block cells, so its LVS
reference has to be one flat netlist too. This module composes it from the
five blocks' *own* ``reference_netlist()`` outputs -- each already the
reference its block's evidence-directory LVS run matched or reported against
-- rather than re-deriving 809 devices a third time. The wiring between the
blocks is read from ``design/netlist/pll_top.spice`` itself
(:mod:`pll_top.top_level.netlist`), so a schematic change that rewires a
block port breaks this composition instead of silently desynchronising it.

Three deliberate, disclosed deviations from "concatenate the block
references":

* **The substrate merge.** The deck models the p-substrate as one global
  node named by ``--lvs_sub``, so ``VSS`` and ``GND_VCO`` -- separate
  *metal* nets of ``pll_top`` -- extract as one node. The composition maps
  ``GND_VCO`` to ``VSS`` (``SUBSTRATE_MERGE``); that the *routing* keeps the
  two apart is graded separately by ``netcheck.py``, whose own docstring
  states the same two-nets-one-substrate fact from the extraction side.
  Run the deck with ``--lvs-sub VSS`` (``layout/run_pv.py lvs``'s default).
* **The loop filter stays option A.** ``pll_top.gds`` pins the loop filter
  generator to ``--mim-option A`` (see ``assemble.BLOCKS``'s own comment:
  the committed assembly is the DR-006 option-A filter; re-assembling with
  the DR-042 option-B device is follow-up work, tracked at #753). The
  composed reference therefore requests ``mim_option="A"`` too, so the one
  known device delta between the committed design netlist (option B since
  DR-042's schematic preparation) and the committed layout does not mask
  every other comparison.
* **Internal names are path-qualified.** Each instance's devices and
  internal nets get its instance name (``XPFD``/``XLF``/``XVCO``/``XDIV``/
  ``XLD``) as a prefix, the same convention ``divider_chain.py``'s
  ``_instance_body`` and ``harness.spice_flatten`` use, so two blocks'
  internal nets can never merge by name collision in the flat reference.

Everything else is mechanical: device cards (``M_``/``R_``/``C_`` lines)
are retokenised with ``harness.spice_flatten``'s own tokenizer, port
tokens are mapped to the ``pll_top`` nets the instance line names, PDK
model names and ``KEY=value`` parameters pass through, and any other bare
token is an internal net and is prefixed. A composed card that does not
carry exactly one PDK model token fails loudly rather than silently
emitting a line the deck would mis-parse.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

from . import netlist as NL

#: The PDK device models the five blocks' references name. A bare token that
#: is not a mapped port, not a ``KEY=value`` parameter and not in this set is
#: an internal net and gets path-qualified; a card with zero or several
#: model tokens is a composition bug and raises.
DEVICE_MODELS = frozenset(
    {
        "pfet_03v3",
        "nfet_03v3",
        "cap_nmos_03v3",
        "cap_nmos_03v3_b",
        "cap_mim_2f0_m2m3_noshield",
        "cap_mim_2f0_m4m5_noshield",
        "ppolyf_u",
        "ppolyf_u_1k",
        "ppolyf_u_2k",
        "ppolyf_u_3k",
    }
)

#: The two substrate-domain nets ``pll_top.spice`` declares, and the one node
#: the deck's p-substrate actually is -- see the module docstring.
SUBSTRATE_MERGE = {"GND_VCO": "VSS"}

TOP_CELL = "pll_top"

_DEVICE_CARD_PREFIXES = ("M_", "R_", "C_")

#: subckt name (as ``design/netlist/pll_top.spice`` instantiates it) ->
#: (module path, reference_netlist keyword arguments). The module paths are
#: ``assemble.BLOCKS``' own, reused rather than restated.
_BLOCK_REFERENCES: dict[str, tuple[str, dict[str, str]]] = {
    "lock_detector": ("pll_top.lock_detector.build", {}),
    "pfd_cp": ("pll_top.pfd_cp.block", {}),
    "loop_filter": ("pll_top.loop_filter.block", {"mim_option": "A"}),
    "vco": ("pll_top.vco.block", {}),
    "divider_chain": ("pll_top.divider_chain.divider_chain", {}),
}


def _harness():
    """Import ``layout/harness`` by putting ``LAYOUT_DIR`` on ``sys.path``.

    ``layout/run_pv.py``, ``layout/tests/_env.py`` and every block CLI do
    the same insert; this module is reachable from both worlds (CLI and
    unittest), so it performs the insert itself instead of assuming either.
    """
    layout_dir = Path(__file__).resolve().parents[2]
    if str(layout_dir) not in sys.path:
        sys.path.insert(0, str(layout_dir))
    from harness import spice_flatten  # noqa: PLC0415

    return spice_flatten


def _block_reference_text(subckt: str) -> str:
    """One block's own ``reference_netlist()`` output, imported lazily.

    The block modules pull in the klayout pip wheel through their geometry
    code, so this import -- like everything else in this package -- runs
    under the PV python (``layout/run_pv.py check-env`` names it).
    """
    module_name, kwargs = _BLOCK_REFERENCES[subckt]
    module = importlib.import_module(module_name)
    return module.reference_netlist(**kwargs)


def _compose_card(line: str, prefix: str, port_map: dict[str, str], tokenize) -> str:
    """Retokenise one device card for one flattened instance.

    Device name keeps its letter prefix (``M_``/``R_``/``C_``) and gains the
    instance prefix; ports map to ``pll_top`` nets; models and parameters
    pass through; any other bare token is an internal net and gains the
    prefix. Raises on a card whose model-token count is not exactly one --
    that is a composition bug (an unmapped net that happens to equal a model
    name, or a card type this module does not know), not something to emit
    and let the deck mis-read.
    """
    tokens = tokenize(line)
    name, rest = tokens[0], tokens[1:]
    renamed = f"{name[0]}_{prefix}_{name[2:]}"
    out = [renamed]
    models = 0
    for token in rest:
        if token in port_map:
            out.append(port_map[token])
        elif "=" in token:
            out.append(token)
        elif token in DEVICE_MODELS:
            out.append(token)
            models += 1
        else:
            out.append(f"{prefix}_{token}")
    if models != 1:
        raise ValueError(
            f"card {renamed!r} carries {models} PDK model tokens (need exactly 1); "
            f"the composed line would not parse as one device"
        )
    return " ".join(out)


def top_reference_netlist() -> str:
    """The flat ``pll_top`` LVS reference, composed as the docstring states."""
    sf = _harness()
    nl = NL.read()
    body: list[str] = []
    for inst in nl.instances:
        if inst.subckt not in _BLOCK_REFERENCES:
            raise ValueError(
                f"pll_top.spice instantiates {inst.subckt!r}, which has no block reference"
            )
        port_map = dict(zip(inst.ports, inst.nets))
        port_map.update(SUBSTRATE_MERGE)
        ref_text = _block_reference_text(inst.subckt)
        cards = [line for line in ref_text.splitlines() if line.startswith(_DEVICE_CARD_PREFIXES)]
        if not cards:
            raise ValueError(f"{inst.subckt}'s reference_netlist() emitted no device cards")
        body.extend(
            _compose_card(line, inst.name, port_map, sf._tokenize) for line in cards
        )
    lines = [
        f"* Flat LVS reference for the assembled pll_top (issues #237, #149),",
        "* composed by layout/pll_top/top_level/reference.py from the five blocks'",
        "* own reference_netlist() outputs; wiring read from design/netlist/pll_top.spice.",
        f".subckt {TOP_CELL} {' '.join(nl.pins)}",
        *body,
        f".ends {TOP_CELL}",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Write the flat pll_top LVS reference netlist (issues #237, #149)."
    )
    parser.add_argument("--outdir", required=True)
    args = parser.parse_args(argv)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / "pll_top.spice"
    path.write_text(top_reference_netlist())
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
