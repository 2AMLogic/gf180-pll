"""Run the PDK's own ``run_lvs.py`` with the ``poly_res`` switch overridden.

``$PDK_ROOT/libs.tech/klayout/lvs/gf180mcu.lvs`` reads the high-sheet
poly-resistor process option from a ``-rd poly_res=<1k|2k|3k>`` klayout
variable (``POLY_RES = $poly_res || '1k'``), and
``rule_decks/res_extraction.lvs``'s ``case POLY_RES`` block is what decides
whether a marked (GDS ``(62, 0)``) poly resistor extracts as ``ppolyf_u_1k``,
``ppolyf_u_2k`` or ``ppolyf_u_3k``. The PDK's own ``run_lvs.py`` **hardcodes**
``switches["poly_res"] = "1k"`` for every one of its four ``--variant``
letters and exposes no CLI override (gf180mcuD, open_pdks
``c6d73a35f524070e85faff4a6a9eef49553ebc2b``; the variant letters select the
metal stack and MIM option, which are independent of the poly option).

This shim exists so this repo can state its own ratified process option (see
``spec/decision-records/DR-009-vco-bias-resistor-device-class.md``) without
forking the deck or re-deriving the PDK's ~20 other switch values, which
would silently drift from the PDK on the next release. It imports the PDK's
runner as a module, re-uses that runner's **own** docopt parsing and **own**
``generate_klayout_switches()`` to build the switch set, replaces exactly one
key, and then calls the runner's own ``main()``. Everything else -- the deck
file, the klayout invocation, the report/target-netlist paths -- is the
PDK's, unmodified.

Usage (invoked by ``layout/harness/lvs.py``, not by hand)::

    <pv-python> _pdk_lvs_poly_res.py <run_lvs.py> <poly_res> <run_lvs args...>
"""

from __future__ import annotations

import importlib.util
import logging
import os
import sys


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2

    runner_path, poly_res, runner_argv = argv[0], argv[1], argv[2:]

    spec = importlib.util.spec_from_file_location("pdk_run_lvs", runner_path)
    if spec is None or spec.loader is None:  # pragma: no cover - operational
        print(f"cannot import the PDK LVS runner at {runner_path}", file=sys.stderr)
        return 2
    module = importlib.util.module_from_spec(spec)
    sys.modules["pdk_run_lvs"] = module
    spec.loader.exec_module(module)

    from docopt import docopt

    arguments = docopt(module.__doc__, argv=runner_argv, version="RUN LVS: 1.0")

    original = module.generate_klayout_switches

    def with_poly_res(args, layout_path, netlist_path):
        switches = original(args, layout_path, netlist_path)
        switches["poly_res"] = poly_res
        return switches

    module.generate_klayout_switches = with_poly_res

    run_dir = os.path.abspath(arguments["--run_dir"])
    os.makedirs(run_dir, exist_ok=True)
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[logging.StreamHandler()],
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%d-%b-%Y %H:%M:%S",
    )
    logging.info(f"poly_res switch overridden to {poly_res} (see {__file__})")

    module.main(run_dir, arguments)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
