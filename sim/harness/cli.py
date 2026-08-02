"""Command line front end: ``python3 sim/run_corners.py <testbench> [...]``."""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import sys
import time
from pathlib import Path

from . import HARNESS_VERSION, corners as corners_mod, report, runner, testbench as tb_mod
from . import derived as derived_mod
from . import raw_measures as raw_measures_mod
from .pdk import PdkNotFound, find_pdk
from .runner import NgspiceMissing

REPO_ROOT = Path(__file__).resolve().parents[2]
SIM_DIR = REPO_ROOT / "sim"

EXIT_OK = 0
EXIT_CHECK_FAILED = 1
EXIT_SIM_ERROR = 2
EXIT_ENVIRONMENT = 3


def _has_manifest(candidate: Path) -> bool:
    if candidate.is_file() and candidate.name == tb_mod.MANIFEST_NAME:
        return True
    if (candidate / tb_mod.MANIFEST_NAME).is_file():
        return True
    return (candidate / tb_mod.TESTBENCH_DIRNAME / tb_mod.MANIFEST_NAME).is_file()


def _resolve_tb_path(argument: str) -> Path:
    """Accept an experiment slug, an experiment dir, or a testbench dir."""
    candidates = [Path(argument), SIM_DIR / argument]
    for candidate in candidates:
        if _has_manifest(candidate):
            return candidate
    raise FileNotFoundError(
        f"no experiment {argument!r}; tried: "
        + ", ".join(str(c) for c in candidates)
        + ".\nAvailable: "
        + ", ".join(p.name for p in tb_mod.discover(SIM_DIR))
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_corners.py",
        description="Run a testbench across the gf180mcu PVT corner grid.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 sim/run_corners.py harness-selftest\n"
            "  python3 sim/run_corners.py harness-selftest --corners typical --temps 27 \\\n"
            "      --subset-reason 'debugging convergence, not evidence'\n"
            "  python3 sim/run_corners.py harness-selftest --corner-set full -j 8\n"
            "  python3 sim/run_corners.py divider-ratio --axis n=n64 --axis rate=f200 \\\n"
            "      --subset-reason 'retiming worst case only'\n"
            "  python3 sim/run_corners.py divider-ratio \\\n"
            "      --join dff=divider-ratio/corners/<record-id>/dff_setup_hold.csv\n"
            "  python3 sim/run_corners.py --list\n"
            "  python3 sim/run_corners.py --check-env\n"
        ),
    )
    parser.add_argument(
        "testbench",
        nargs="?",
        metavar="EXPERIMENT",
        help="experiment slug under sim/ (i.e. sim/<slug>/testbench/tb.json)",
    )
    parser.add_argument("--list", action="store_true", help="list testbenches and corners")
    parser.add_argument(
        "--check-env",
        action="store_true",
        help="report ngspice / PDK availability and exit",
    )
    parser.add_argument(
        "--print-env",
        action="store_true",
        help="print shell exports for the resolved PDK (used by sim/env.sh)",
    )
    parser.add_argument(
        "--corners",
        nargs="+",
        metavar="NAME",
        help="explicit corner or corner-set names (overrides the manifest)",
    )
    parser.add_argument(
        "--corner-set",
        choices=sorted(corners_mod.CORNER_SETS),
        help="shorthand for --corners <set>",
    )
    parser.add_argument(
        "--temps",
        nargs="+",
        type=float,
        metavar="C",
        help="temperatures in degrees C (overrides the manifest)",
    )
    parser.add_argument(
        "--supply",
        type=float,
        metavar="V",
        help="nominal supply in volts (overrides the manifest)",
    )
    parser.add_argument(
        "--supply-tol",
        type=float,
        metavar="FRAC",
        help="supply tolerance as a fraction, e.g. 0.10 (0 disables the V axis)",
    )
    parser.add_argument(
        "--axis",
        action="append",
        default=[],
        metavar="NAME=ID[,ID...]",
        help="restrict an extra sweep axis declared in the manifest's 'sweeps' to "
        "the named point ids (repeatable); a run thinned this way is a PVT/axis "
        "subset and needs --subset-reason or --no-write like any other",
    )
    parser.add_argument(
        "--join",
        action="append",
        default=[],
        metavar="ALIAS=PATH",
        help="supply or override a derived-metric join input: a CSV written by "
        "another record, path relative to sim/ (repeatable)",
    )
    parser.add_argument("-j", "--jobs", type=int, default=0, help="parallel ngspice runs")
    parser.add_argument(
        "--timeout",
        type=int,
        default=runner.DEFAULT_TIMEOUT_S,
        help="per-point ngspice timeout in seconds",
    )
    parser.add_argument(
        "--claim",
        default="",
        help="spec line or design-input question this run substantiates, e.g. "
        "'spec/pll.md#lock-time' or '#4 -> #8: ...' (overrides the manifest's 'claim')",
    )
    parser.add_argument(
        "--supersedes",
        default="",
        metavar="RECORD_ID",
        help="prior record-id this record corrects or replaces",
    )
    parser.add_argument(
        "--supersedes-note",
        default="",
        metavar="TEXT",
        help="free-text qualifier for --supersedes stating which part of the "
        "predecessor is superseded, e.g. 'switching-timing half only' -- "
        "rendered as '**Supersedes**: <id> -- <note>' (see sim/README.md's "
        "per-bench supersession scoping); ignored if --supersedes is not set",
    )
    parser.add_argument(
        "--statistical-convention",
        default="",
        metavar="TEXT",
        help="N samples / sigma level, for distribution (Monte Carlo) claims",
    )
    parser.add_argument(
        "--subset-reason",
        default="",
        metavar="TEXT",
        help="why this run is not the full mandated PVT matrix; required before "
        "a subset run may be recorded as evidence",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="run but do not record evidence (debugging only)",
    )
    parser.add_argument("--quiet", action="store_true", help="only print the summary")
    parser.add_argument("--version", action="version", version=f"gf180-pll harness {HARNESS_VERSION}")
    return parser


def cmd_list() -> int:
    print("Experiments (sim/<slug>/testbench/tb.json):")
    for directory in tb_mod.discover(SIM_DIR):
        try:
            tb = tb_mod.load(directory)
            print(f"  {directory.name:<20} {tb.description or tb.name}")
        except Exception as exc:  # noqa: BLE001 - surface bad manifests, keep listing
            print(f"  {directory.name:<20} !! {exc}")
    print("\nCorner sets:")
    for name, members in sorted(corners_mod.CORNER_SETS.items()):
        print(f"  {name:<20} {', '.join(members)}")
    print("\nCorners:")
    for name, corner in corners_mod.CORNERS.items():
        print(f"  {name:<20} {corner.description}")
        print(f"  {'':<20} sections: {' '.join(corner.sections)}")
    return EXIT_OK


def cmd_check_env() -> int:
    status = EXIT_OK
    try:
        version = runner.ngspice_version()
        print(f"ngspice : OK   {version}")
    except NgspiceMissing as exc:
        print(f"ngspice : MISSING\n{exc}")
        status = EXIT_ENVIRONMENT
    try:
        pdk = find_pdk()
        print(f"PDK     : OK   {pdk.path} (open_pdks {pdk.version}, via {pdk.source})")
        print(f"  models: {pdk.model_lib}")
        print(f"  xschem: {pdk.xschem_dir}")
    except PdkNotFound as exc:
        print(f"PDK     : MISSING\n{exc}")
        status = EXIT_ENVIRONMENT
    return status


def cmd_print_env() -> int:
    """Emit shell exports so xschem/ngspice see the same PDK the harness picked."""
    try:
        pdk = find_pdk()
    except PdkNotFound as exc:
        print(f"# gf180mcu PDK not found\n# {exc.args[0].splitlines()[0]}", file=sys.stderr)
        return EXIT_ENVIRONMENT
    library_path = ":".join(
        str(p)
        for p in [REPO_ROOT / "design"]
        + [d / tb_mod.TESTBENCH_DIRNAME for d in tb_mod.discover(SIM_DIR)]
    )
    print(f'export PDK_ROOT="{pdk.path.parent}"')
    print(f'export PDK="{pdk.variant}"')
    print(f'export GF180_PDK_PATH="{pdk.path}"')
    print(f'export GF180_PDK_ROOT="{pdk.path}"')
    print(f'export GF180_MODELS="{pdk.ngspice_dir}"')
    print(f'export XSCHEM_USER_LIBRARY_PATH="{library_path}"')
    return EXIT_OK


def parse_key_value(entries: list[str], flag: str) -> dict[str, str]:
    """``["a=b", "c=d"]`` -> ``{"a": "b", "c": "d"}``, for ``--axis`` / ``--join``."""
    out: dict[str, str] = {}
    for entry in entries or []:
        if "=" not in entry:
            raise ValueError(f"{flag} expects NAME=VALUE, got {entry!r}")
        key, _, value = entry.partition("=")
        key = key.strip()
        if not key or not value.strip():
            raise ValueError(f"{flag} expects NAME=VALUE, got {entry!r}")
        out[key] = value.strip()
    return out


def parse_axis_filters(entries: list[str]) -> dict[str, list[str]]:
    """``--axis n=n04,n64`` -> ``{"n": ["n04", "n64"]}``."""
    return {
        name: [i for i in value.split(",") if i]
        for name, value in parse_key_value(entries, "--axis").items()
    }


def build_derived_tables(tb, results, join_args: list[str]) -> list:
    """Run the campaign's ``derive_tables()``, if the manifest declares any.

    Join inputs come from the manifest's ``derived.joins`` map, overridden per
    invocation by ``--join alias=path``: a cross-record join names *another
    record's* CSV, and a committed manifest cannot know which record id a given
    run is being closed against.

    Each point's own ``raw_files`` are carried through onto its ``PointView``
    as well, so a whole-run reduction over per-point waveforms (a jitter table,
    a family of I-V curves) can reach them the same way ``derive_point`` does.
    Nothing deletes the run's work directory, so the scratch copies are still
    on disk here, after every point has run.
    """
    spec = getattr(tb, "derived", None)
    if spec is None or not spec.tables:
        return []
    wanted = dict(spec.joins)
    wanted.update(parse_key_value(join_args, "--join"))
    joins = {}
    for alias, rel in wanted.items():
        path = Path(rel)
        if not path.is_absolute():
            path = SIM_DIR / rel
        joins[alias] = derived_mod.read_join_csv(alias, path)
    view = derived_mod.RunView(
        experiment=tb.experiment,
        measure_names=tuple(tb.measure_names),
        points=tuple(
            derived_mod.PointView(
                corner=r.point.corner.name,
                corner_id=r.point.corner_id,
                temp_c=r.point.temp_c,
                vdd=r.point.vdd,
                axes=r.point.axes,
                params=r.point.params,
                measurements=dict(r.measurements),
                raw_files=dict(r.raw_files),
            )
            for r in results
            if r.status == "ok"
        ),
        joins=joins,
    )
    return derived_mod.derive_run_tables(spec, view)


def _fmt(value) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        if value != 0 and (abs(value) < 1e-3 or abs(value) >= 1e5):
            return f"{value:.6e}"
        return f"{value:.6g}"
    return str(value)


def run(args: argparse.Namespace) -> int:
    tb_path = _resolve_tb_path(args.testbench)
    tb = tb_mod.load(tb_path)

    try:
        pdk = find_pdk()
        ngspice = runner.ngspice_version()
    except (PdkNotFound, NgspiceMissing) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ENVIRONMENT

    corner_names = args.corners or ([args.corner_set] if args.corner_set else list(tb.corners))
    corner_list = corners_mod.resolve_corners(corner_names)
    temperatures = args.temps if args.temps is not None else list(tb.temperatures_c)
    nominal = args.supply if args.supply is not None else tb.nominal_supply_v
    tolerance = args.supply_tol if args.supply_tol is not None else tb.supply_tolerance
    supplies = corners_mod.supply_points(nominal, tolerance)
    points = corners_mod.build_sweep_grid(
        corner_list,
        temperatures,
        supplies,
        axes=tb.sweeps,
        blocks=tb.grid_blocks,
        axis_filter=parse_axis_filters(args.axis),
    )
    if not points:
        print(
            "error: this run resolved to zero points -- the manifest's grid blocks "
            "and the axes you asked for do not intersect.",
            file=sys.stderr,
        )
        return EXIT_ENVIRONMENT

    # sim/README.md: an evidence record must cover the full mandated PVT
    # matrix unless it states why a subset was used. Refuse to record a thin
    # run without that justification rather than quietly banking weak evidence.
    conformance = report.matrix_conformance(tb, points)
    # A deliberately thinned *extra* axis is justified by the manifest's own
    # per-block descriptions and needs no CLI flag. An axis the CLI narrowed
    # (--axis) or a block that came up empty is a different thing: the record
    # would claim coverage this invocation does not have, so it is treated
    # exactly like a PVT subset and needs a written reason.
    axis_gaps = [
        f"sweep axis {a['name']}: missing point(s) " + ", ".join(a["missing"])
        for a in conformance.get("axes", [])
        if a["missing"]
    ] + [
        f"grid block produced no points: {d}"
        for d in conformance.get("empty_blocks", [])
    ]
    if axis_gaps:
        conformance = dict(conformance)
        conformance["full"] = False
        conformance["missing"] = list(conformance["missing"]) + axis_gaps
    if not args.no_write and not conformance["full"] and not args.subset_reason:
        print(
            "error: this run is a subset of the PVT matrix CLAUDE.md/sim/README.md mandate:\n  - "
            + "\n  - ".join(conformance["missing"])
            + "\nRecord it with --subset-reason '<why>', or re-run the full matrix,"
            "\nor use --no-write if this is just a debugging run.",
            file=sys.stderr,
        )
        return EXIT_ENVIRONMENT

    experiment_dir = tb.experiment_dir
    records_dir = experiment_dir / report.RECORDS_DIR

    jobs = args.jobs or min(8, (os.cpu_count() or 2))
    started = _dt.datetime.now(_dt.timezone.utc)
    # Sample git state *before* the run: the harness writes its own per-corner
    # logs into the tracked evidence tree, so sampling afterwards would mark
    # every record as taken against a dirty tree.
    git = report.git_provenance(REPO_ROOT)
    record_id = report.allocate_record_id(REPO_ROOT, records_dir, started, git=git)
    workdir = experiment_dir / "work" / record_id
    log_dir = None if args.no_write else experiment_dir / report.CORNERS_DIR / record_id

    if not args.quiet:
        print(f"experiment: {tb.experiment}"
              + (f"  ({tb.description})" if tb.description else ""))
        print(f"pdk       : {pdk.variant} @ {pdk.version}  ({pdk.path})")
        print(f"ngspice   : {ngspice}")
        print(f"corners   : {', '.join(c.name for c in corner_list)}")
        print(f"temps (C) : {', '.join(_fmt(t) for t in temperatures)}")
        print(f"supply (V): {', '.join(_fmt(v) for v in supplies)} "
              f"(nominal {_fmt(nominal)} +/-{tolerance * 100:g}%)")
        for axis in conformance.get("axes", []):
            print(f"axis {axis['name']:<6}: {', '.join(axis['ran'])}")
        print(f"points    : {len(points)}  (jobs={jobs})")
        print(f"record id : {record_id}")
        print()
    for description in conformance.get("empty_blocks", []):
        print(
            f"warning: grid block produced no points: {description}", file=sys.stderr
        )

    completed = 0

    def progress(result):
        nonlocal completed
        completed += 1
        if args.quiet:
            return
        flag = {"ok": "ok  ", "failed": "FAIL", "error": "ERR "}[result.status]
        detail = ""
        if result.status == "ok":
            detail = "  ".join(
                f"{name}={_fmt(result.measurements[name])}" for name in tb.measure_names
                if name in result.measurements
            )
        else:
            detail = result.message
        print(f"[{completed:>3}/{len(points)}] {flag} {result.point.corner_id:<26} {detail}")

    wall_start = time.monotonic()
    try:
        results = runner.run_grid(
            tb,
            pdk,
            points,
            workdir,
            jobs=jobs,
            timeout_s=args.timeout,
            on_result=progress,
            log_dir=log_dir,
        )
    except NgspiceMissing as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ENVIRONMENT
    wall = time.monotonic() - wall_start

    # Derived metrics: the campaign's own reduction over the table above, which
    # is what its record actually claims. Run before the record is built so a
    # broken reduction fails the run rather than minting a record without it.
    try:
        derived_tables = build_derived_tables(tb, results, args.join)
    except (derived_mod.DerivedError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_SIM_ERROR

    record = report.build_record(
        tb=tb,
        pdk=pdk,
        points=points,
        results=results,
        ngspice=ngspice,
        repo_root=REPO_ROOT,
        record_id=record_id,
        started_utc=started.isoformat(timespec="seconds"),
        wall_seconds=wall,
        claim=args.claim,
        supersedes=args.supersedes,
        supersedes_note=args.supersedes_note,
        statistical_convention=args.statistical_convention,
        subset_reason=args.subset_reason,
        git=git,
        derived_tables=derived_tables,
        conformance=conformance,
    )

    print()
    print(f"summary ({record['grid']['points_ok']}/{len(points)} points ok, {wall:.1f}s):")
    header = f"  {'measurement':<16}{'min':>16}{'max':>16}{'mean':>16}{'spread %':>12}"
    print(header)
    for name, stats in record["summary"].items():
        if not stats.get("n"):
            label = "not measured" if stats.get("optional") else "no data"
            print(f"  {name:<16}{label:>16}")
            continue
        print(
            f"  {name:<16}{_fmt(stats['min']):>16}{_fmt(stats['max']):>16}"
            f"{_fmt(stats['mean']):>16}{_fmt(stats['spread_pct']):>12}"
        )

    for failure in record["checks"]["failures"]:
        print(
            f"  CHECK FAIL {failure['measurement']} {failure['kind']}={_fmt(failure['limit'])} "
            f"got {_fmt(failure['value'])} at {failure['at']}"
        )

    # A declared raw file the deck never wrote is data, not an error -- but it
    # is data worth saying out loud, because it silently starves whatever
    # reduction was supposed to read it.
    for name in tb.raw_file_names:
        absent = [r.point.corner_id for r in results if name in r.raw_files_missing]
        if absent:
            print(
                f"  raw file {name!r} not written at {len(absent)}/{len(results)} "
                f"point(s): {', '.join(absent[:3])}"
                + (" ..." if len(absent) > 3 else "")
            )

    if not args.no_write:
        snapshot = report.write_netlist_snapshot(tb, experiment_dir, record_id)
        written = derived_mod.write_derived_tables(derived_tables, log_dir)
        # Always written, regardless of whether the manifest declares any
        # derived.tables -- the per-point raw measurements are evidence in
        # their own right, and a testbench with no derived table would
        # otherwise leave nothing machine-readable behind (sim/harness#110).
        raw_measures_path = raw_measures_mod.write_raw_measures_csv(tb, results, log_dir)
        record_path = report.write_record(record, experiment_dir)
        print()
        print(f"record    : {record_path}")
        print(f"snapshot  : {snapshot}")
        print(f"raw logs  : {log_dir}")
        for spec in tb.raw_files:
            if not spec.retain:
                continue
            kept = sum(
                1
                for r in results
                if spec.name in r.raw_files and r.raw_files[spec.name].exists()
            )
            print(f"raw files : {kept} x <corner-id>-{spec.name} in {log_dir}")
        print(f"raw table : {raw_measures_path}")
        for path in written:
            print(f"derived   : {path}")
    else:
        print()
        print("evidence  : not recorded (--no-write)")
    print(f"work dir  : {workdir}")
    print(f"status    : {record['status'].upper()}")

    if record["status"] == "error":
        return EXIT_SIM_ERROR
    if record["status"] == "fail":
        return EXIT_CHECK_FAILED
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list:
        return cmd_list()
    if args.check_env:
        return cmd_check_env()
    if args.print_env:
        return cmd_print_env()
    if not args.testbench:
        parser.print_help()
        return EXIT_ENVIRONMENT
    try:
        return run(args)
    except (
        FileNotFoundError,
        ValueError,
        KeyError,
        report.RecordExists,
        derived_mod.DerivedError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ENVIRONMENT
