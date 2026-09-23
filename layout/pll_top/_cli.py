"""Shared ``main()`` CLI entry point for ``layout/pll_top/*`` leaf-cell
modules (issue #485).

Nine leaf-cell modules -- ``divider_chain``'s ``inv_3v3``, ``inv2x_3v3``,
``nand2_3v3``, ``nand3_3v3``, ``nor2_3v3`` and ``tgate_3v3``, and
``pfd_cp``'s ``cp_leg_n``, ``cp_leg_p`` and ``pfdcp_inv`` -- each carried
its own byte-for-byte-identical ``main()``: parse ``--outdir``, call the
module's ``build()``, write its ``reference_netlist()`` beside the GDS, and
print the footprint and pin list. Organic duplication (each module was
written by copying a sibling as a template), unlike ``_canvas.py``'s
acknowledged-convention case -- but the same remedy applies, and
``_canvas.py`` is the precedent this module follows for where such a shared
home lives and how it is named (issue #317).

The only real per-module delta was the evidence sub-directory name the
default ``--outdir`` points into (``"divider-rowcells-proof"``,
``"divider-tgate-proof"``, ``"cp-leg-proof"``, ...), so that is the one
positional this helper cannot default; ``description`` is the second, and
only because ``argparse.ArgumentParser(description=__doc__)`` has to keep
reading the *calling* module's docstring rather than this one's, or every
cell's ``--help`` would describe the CLI helper instead of the cell.

``EVIDENCE_ROOT`` is anchored on this module's own path rather than each
caller's, which is the one mechanical change: every one of the nine
modules sits exactly two levels below ``layout/`` (``pll_top/<block>/<cell>.py``)
and spelled this as ``Path(__file__).resolve().parents[2]``; this module
sits one level below (``pll_top/_cli.py``), so the same directory is
``parents[1]``. Same resolved path, so every printed line and every written
file is unchanged -- verified by running all nine modules standalone before
and after and diffing their stdout, their ``--help``, their emitted SPICE
bytes, and their emitted GDS *geometry* (per-layer shape and text dump, not
a checksum -- GDS embeds a write timestamp, so two runs of identical code
already differ by four bytes; the same reason
``layout/harness/reproduce.py`` compares by XOR).

These are developer-only entry points for rebuilding one leaf cell's
evidence GDS + reference netlist in isolation (``python3 -m
pll_top.divider_chain.inv_3v3`` from ``layout/``). Nothing in
``layout/tests/`` or ``layout/run_pv.py`` invokes them, and the blocks that
*compose* these cells import ``build()`` directly -- so this module is on no
verification path and imports nothing heavier than ``pathlib``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Protocol

#: ``layout/evidence`` -- the tree every leaf cell's default ``--outdir``
#: points into. See the module docstring on why this is ``parents[1]`` here
#: where each caller spelled it ``parents[2]``.
EVIDENCE_ROOT = Path(__file__).resolve().parents[1] / "evidence"


class LeafLayout(Protocol):
    """What :func:`leaf_cli_main` needs back from a cell's ``build()``.

    Structurally satisfied by both ``divider_chain/devgen.py``'s
    ``LeafCell`` and ``pfd_cp/cp_leg.py``'s ``LegLayout`` -- the two
    unrelated dataclasses the nine callers return -- without either of them
    having to inherit anything.
    """

    pins: dict[str, tuple[float, float, float, float]]
    footprint: tuple[float, float, float, float]


def leaf_cli_main(
    build: Callable[[Path], LeafLayout],
    top_cell: str,
    reference_netlist: Callable[[], str],
    evidence_subdir: str,
    *,
    description: str | None = None,
) -> int:
    """Build one leaf cell into ``--outdir`` and report what was written.

    ``build``/``top_cell``/``reference_netlist`` are the calling module's
    own; ``evidence_subdir`` names its directory under
    :data:`EVIDENCE_ROOT`; ``description`` should be the calling module's
    ``__doc__`` (see the module docstring).
    """
    # Deferred, as in each caller's own original ``main()``: every one of the
    # nine modules now imports this one at module scope (and the blocks that
    # compose them import those), so a top-level ``import argparse`` here
    # would pull argparse into every one of those import chains for a CLI
    # path none of them takes.
    import argparse  # noqa: PLC0415

    parser = argparse.ArgumentParser(description=description)
    default_outdir = EVIDENCE_ROOT / evidence_subdir / "work"
    parser.add_argument("--outdir", default=str(default_outdir))
    args = parser.parse_args()
    outdir = Path(args.outdir)
    layout = build(outdir)
    netlist_path = outdir / f"{top_cell}.spice"
    netlist_path.write_text(reference_netlist())
    x0, y0, x1, y1 = layout.footprint
    print(f"wrote {outdir}/{top_cell}.gds")
    print(f"wrote {netlist_path}")
    print(f"footprint: {x1 - x0:.3f} x {y1 - y0:.3f} um  ({(x1 - x0) * (y1 - y0):.2f} um^2)")
    print(f"pins: {sorted(layout.pins)}")
    return 0
