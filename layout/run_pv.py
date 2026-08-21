#!/usr/bin/env python3
"""CLI front end for the gf180mcu DRC/LVS flow: ``python3 layout/run_pv.py <command>``.

See ``layout/README.md`` for the full flow write-up (what each command does,
how to read a result, tool/PDK prerequisites). Quick reference:

    python3 layout/run_pv.py check-env          # is the PDK / KLayout / a PV python present?
    python3 layout/run_pv.py build               # assemble inv_tb.gds + inv_tb.spice
    python3 layout/run_pv.py drc <gds> --top T   # run the foundry DRC deck
    python3 layout/run_pv.py lvs <gds> <net> --top T
    python3 layout/run_pv.py prove               # the full proof: clean run + 2 negative controls

Exit codes (consistent across drc/lvs/prove):
    0  clean / match -- or, for prove, every expectation (positive and negative) held
    1  violations / mismatch (drc, lvs) -- an unexpected result for that single command
    2  environment problem: PDK, KLayout, or a PV-capable python not found
    3  prove-only: a negative control came back clean -- the harness itself is not
       trustworthy as a gate (see layout/harness/faults.py)
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import cell, drc as drc_mod, env, faults, lvs as lvs_mod  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
LAYOUT_DIR = REPO_ROOT / "layout"
EVIDENCE_DIR = LAYOUT_DIR / "evidence"

EXIT_OK = 0
EXIT_UNEXPECTED_RESULT = 1
EXIT_ENVIRONMENT = 2
EXIT_HARNESS_UNTRUSTWORTHY = 3


def _find_tools(args: argparse.Namespace) -> env.PvTools | None:
    try:
        return env.find_tools(args.variant)
    except (env.PdkNotFound, env.ToolNotFound) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return None


def cmd_check_env(_args: argparse.Namespace) -> int:
    tools = _find_tools(_args)
    if tools is None:
        return EXIT_ENVIRONMENT
    print(f"PDK        : OK   {tools.pdk.path} (variant {tools.variant_letter}, "
          f"open_pdks {tools.pdk.version})")
    print(f"KLayout    : OK   {tools.klayout} ({tools.klayout_version()})")
    print(f"PV python  : OK   {tools.python}")
    print(f"DRC runner : {tools.drc_runner}")
    print(f"LVS runner : {tools.lvs_runner}")
    print(f"stdcell gds: {tools.stdcell_gds}")
    return EXIT_OK


def cmd_build(args: argparse.Namespace) -> int:
    tools = _find_tools(args)
    if tools is None:
        return EXIT_ENVIRONMENT
    outdir = Path(args.outdir)
    tc = cell.build(outdir, tools.stdcell_gds)
    print(f"gds     : {tc.gds}")
    print(f"netlist : {tc.netlist}")
    print(f"topcell : {tc.topcell}")
    return EXIT_OK


def cmd_drc(args: argparse.Namespace) -> int:
    tools = _find_tools(args)
    if tools is None:
        return EXIT_ENVIRONMENT
    result = drc_mod.run(
        args.layout,
        args.top,
        args.run_dir,
        tools=tools,
        run_mode=args.run_mode,
        offgrid=args.offgrid,
        timeout=args.timeout,
    )
    print(result.summary())
    if result.status == "error":
        return EXIT_ENVIRONMENT
    return EXIT_OK if result.ok else EXIT_UNEXPECTED_RESULT


def cmd_lvs(args: argparse.Namespace) -> int:
    tools = _find_tools(args)
    if tools is None:
        return EXIT_ENVIRONMENT
    result = lvs_mod.run(
        args.layout,
        args.netlist,
        args.top,
        args.run_dir,
        tools=tools,
        run_mode=args.run_mode,
        substrate=args.lvs_sub,
        timeout=args.timeout,
    )
    print(result.summary())
    if result.status == "error":
        return EXIT_ENVIRONMENT
    return EXIT_OK if result.ok else EXIT_UNEXPECTED_RESULT


def cmd_bare_cell(args: argparse.Namespace) -> int:
    """Stream one untapped standard cell and DRC it -- the tap-necessity control.

    Expected to come back DIRTY (DF.13_MV / DF.14_MV-class violations -- see
    layout/harness/cell.py's module docstring). This is *not* part of
    ``prove``'s pass/fail gate: it demonstrates why the row in ``build()``
    carries tie/fill cells, it does not exercise the harness's dirty-result
    detection (``prove``'s negative controls already do that).
    """
    tools = _find_tools(args)
    if tools is None:
        return EXIT_ENVIRONMENT
    outdir = Path(args.outdir)
    gds = cell.build_bare_cell(outdir, tools.stdcell_gds)
    result = drc_mod.run(gds, gds.stem, outdir / "drc", tools=tools, timeout=args.timeout)
    print(result.summary())
    if result.status == "clean":
        print(
            "note: a bare standard cell came back DRC clean -- unexpected (see "
            "layout/harness/cell.py's docstring); this does not fail the command, "
            "but the 'taps are not optional' claim should be re-checked."
        )
    return EXIT_OK if result.status != "error" else EXIT_ENVIRONMENT


def _copy_run_artifacts(run_dir: Path, dest: Path, keep: tuple) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for name in keep:
        for match in run_dir.glob(name):
            shutil.copy2(match, dest / match.name)


def cmd_prove(args: argparse.Namespace) -> int:
    """Run the full flow-bring-up proof and (unless ``--evidence-dir ''``) record it.

    Four checks, each with an *expected* verdict:

    1. inv_tb DRC          -- expected clean
    2. inv_tb LVS           -- expected match
    3. inv_tb + DRC fault   -- expected violations (negative control)
    4. inv_tb + LVS fault   -- expected mismatch  (negative control)

    Exits 0 only if every expectation held. A negative control that comes
    back clean is treated as a harness fault (exit 3), not a pass -- see
    layout/harness/faults.py's module docstring.
    """
    tools = _find_tools(args)
    if tools is None:
        return EXIT_ENVIRONMENT

    work = Path(args.work_dir)
    work.mkdir(parents=True, exist_ok=True)
    evidence_dir = Path(args.evidence_dir) if args.evidence_dir else None

    print(f"pdk        : {tools.pdk.variant} @ {tools.pdk.version} ({tools.pdk.path})")
    print(f"klayout    : {tools.klayout_version()} ({tools.klayout})")
    print(f"work dir   : {work}")
    print()

    checks: list[dict] = []
    all_ok = True
    harness_untrustworthy = False

    tc = cell.build(work, tools.stdcell_gds)
    print(f"built      : {tc.gds.name} + {tc.netlist.name}")

    # --- 1. positive DRC ----------------------------------------------------
    drc_clean_dir = work / "drc-clean"
    r = drc_mod.run(tc.gds, tc.topcell, drc_clean_dir, tools=tools, timeout=args.timeout)
    print(f"[1/4] {r.summary()}")
    checks.append({"name": "inv_tb DRC", "expected": "clean", "got": r.status, "ok": r.ok})
    all_ok &= r.ok

    # --- 2. positive LVS -----------------------------------------------------
    lvs_clean_dir = work / "lvs-clean"
    r2 = lvs_mod.run(tc.gds, tc.netlist, tc.topcell, lvs_clean_dir, tools=tools, timeout=args.timeout)
    print(f"[2/4] {r2.summary()}")
    checks.append({"name": "inv_tb LVS", "expected": "match", "got": r2.status, "ok": r2.ok})
    all_ok &= r2.ok

    # --- 3. DRC negative control ----------------------------------------------
    drc_fault_gds = work / "drc_fault.gds"
    faults.inject_drc_violation(tc.gds, drc_fault_gds)
    drc_fault_dir = work / "drc-fault"
    r3 = drc_mod.run(drc_fault_gds, tc.topcell, drc_fault_dir, tools=tools, timeout=args.timeout)
    r3_ok = r3.status == "violations"
    print(f"[3/4] {r3.summary()}  (negative control -- expected violations)")
    checks.append({"name": "drc_fault DRC", "expected": "violations", "got": r3.status, "ok": r3_ok})
    all_ok &= r3_ok
    if r3.status == "clean":
        harness_untrustworthy = True

    # --- 4. LVS negative control ----------------------------------------------
    lvs_fault_gds = work / "lvs_fault.gds"
    faults.inject_lvs_mismatch(tc.gds, lvs_fault_gds)
    lvs_fault_dir = work / "lvs-fault"
    r4 = lvs_mod.run(lvs_fault_gds, tc.netlist, tc.topcell, lvs_fault_dir, tools=tools, timeout=args.timeout)
    r4_ok = r4.status == "mismatch"
    print(f"[4/4] {r4.summary()}  (negative control -- expected mismatch)")
    checks.append({"name": "lvs_fault LVS", "expected": "mismatch", "got": r4.status, "ok": r4_ok})
    all_ok &= r4_ok
    if r4.status == "match":
        harness_untrustworthy = True

    print()
    for c in checks:
        flag = "ok  " if c["ok"] else "FAIL"
        print(f"  {flag} {c['name']:<16} expected={c['expected']:<11} got={c['got']}")

    if evidence_dir is not None:
        evidence_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(tc.gds, evidence_dir / tc.gds.name)
        shutil.copy2(tc.netlist, evidence_dir / tc.netlist.name)
        _copy_run_artifacts(drc_clean_dir, evidence_dir / "drc-clean", ("*.lyrdb", "drc.stdout.log"))
        _copy_run_artifacts(lvs_clean_dir, evidence_dir / "lvs-clean", ("*.cir", "*.lvsdb", "lvs.stdout.log"))
        shutil.copy2(drc_fault_gds, evidence_dir / drc_fault_gds.name)
        _copy_run_artifacts(drc_fault_dir, evidence_dir / "drc-fault", ("*.lyrdb", "drc.stdout.log"))
        shutil.copy2(lvs_fault_gds, evidence_dir / lvs_fault_gds.name)
        _copy_run_artifacts(lvs_fault_dir, evidence_dir / "lvs-fault", ("*.cir", "*.lvsdb", "lvs.stdout.log"))
        print()
        print(f"evidence   : {evidence_dir}")

    print()
    print(f"status     : {'PASS' if all_ok else 'FAIL'}")

    if harness_untrustworthy:
        return EXIT_HARNESS_UNTRUSTWORTHY
    return EXIT_OK if all_ok else EXIT_UNEXPECTED_RESULT


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_pv.py",
        description="gf180mcu DRC/LVS flow -- see layout/README.md",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--variant", default=None, help="gf180mcu variant letter/name override")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("check-env", help="report PDK / KLayout / PV-python availability")
    p.set_defaults(func=cmd_check_env)

    p = sub.add_parser("build", help="assemble inv_tb.gds + inv_tb.spice")
    p.add_argument("--outdir", default=str(EVIDENCE_DIR / "work"))
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("drc", help="run the foundry DRC deck against a layout")
    p.add_argument("layout")
    p.add_argument("--top", required=True, dest="top")
    p.add_argument("--run-dir", required=True, dest="run_dir")
    p.add_argument("--run-mode", default="deep")
    p.add_argument("--offgrid", action="store_true")
    p.add_argument("--timeout", type=int, default=3600)
    p.set_defaults(func=cmd_drc)

    p = sub.add_parser("lvs", help="run the foundry LVS deck against a layout + reference netlist")
    p.add_argument("layout")
    p.add_argument("netlist")
    p.add_argument("--top", required=True, dest="top")
    p.add_argument("--run-dir", required=True, dest="run_dir")
    p.add_argument("--run-mode", default="deep")
    p.add_argument("--lvs-sub", default="VSS", dest="lvs_sub")
    p.add_argument("--timeout", type=int, default=3600)
    p.set_defaults(func=cmd_lvs)

    p = sub.add_parser(
        "bare-cell",
        help="DRC an untapped standard cell alone -- demonstrates why build() adds tie/fill cells",
    )
    p.add_argument("--outdir", default=str(EVIDENCE_DIR / "work" / "bare-cell"))
    p.add_argument("--timeout", type=int, default=3600)
    p.set_defaults(func=cmd_bare_cell)

    p = sub.add_parser("prove", help="the full proof: clean run + 2 negative controls")
    p.add_argument("--work-dir", default=str(EVIDENCE_DIR / "work" / "prove"))
    p.add_argument(
        "--evidence-dir",
        default=str(EVIDENCE_DIR / "inv-tb-proof"),
        help="where to copy proof artifacts (empty string to skip)",
    )
    p.add_argument("--timeout", type=int, default=3600)
    p.set_defaults(func=cmd_prove)

    return parser


_REEXEC_GUARD = "_GF180_LAYOUT_RUN_PV_REEXECD"


def _reexec_if_klayout_unimportable() -> None:
    """Re-exec under a klayout-capable python if the current one lacks it.

    ``build``/``prove``/``bare-cell`` need ``klayout.db`` importable in *this*
    process (cell assembly, fault injection) -- a separate requirement from
    ``env.find_pv_python()``, which only has to satisfy the PDK's own deck
    runners as a subprocess. A plain system ``python3`` with no ``klayout``
    wheel installed is a completely reasonable way to invoke this script (it
    is what the stdlib-only ``sim/run_corners.py`` expects), so failing with
    a bare ``ModuleNotFoundError`` instead of self-healing would be a rougher
    edge than this harness's tool-discovery design otherwise has anywhere
    else. Guarded by an env var against re-exec looping if the discovered
    interpreter *also* somehow cannot import ``klayout.db`` -- deliberately
    *not* a ``sys.executable == tools.python`` identity check first: a venv's
    ``bin/python`` is commonly a symlink to the very same base interpreter
    binary, so comparing resolved real paths reports "equal" even though
    invoking through the venv path (vs. the base interpreter path directly)
    is exactly what makes the venv's site-packages -- and therefore
    ``klayout`` -- visible. The guard env var is what actually bounds this to
    at most one re-exec.
    """
    if os.environ.get(_REEXEC_GUARD):
        return
    try:
        import klayout.db  # noqa: F401

        return
    except ImportError:
        pass
    try:
        tools = env.find_tools()
    except (env.PdkNotFound, env.ToolNotFound):
        return  # let the actual command surface the real error
    os.environ[_REEXEC_GUARD] = "1"
    os.execv(str(tools.python), [str(tools.python), str(Path(__file__).resolve())] + sys.argv[1:])


def main(argv: list[str] | None = None) -> int:
    _reexec_if_klayout_unimportable()
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return EXIT_ENVIRONMENT
    if hasattr(args, "evidence_dir") and args.evidence_dir == "":
        args.evidence_dir = None
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
