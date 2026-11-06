#!/usr/bin/env python3
"""Staged 45-point grid driver for the period-jitter campaigns.

    sim/period-jitter/grid.py random-bound  [--jobs 2] [--backend local|batch]
    sim/period-jitter/grid.py in-band-bound [--plan]

Each campaign's stages are declared in `<campaign>/grid.json`; the 45 points
come from the campaign's own `run.py` `load_points()` (i.e. `testbench/tb.json`).
The driver turns that into units with dependencies:

    once-only stages  ->  per point: stage1 -> stage2 -> ...  ->  validate
                                                              ->  summarize

and runs them, at most `--jobs` at a time, as `run.py` invocations.  It never
launches ngspice itself; `run.py --backend {local,batch}` decides where decks
run.  `--backend batch` without `--batch-apply` (or `--plan`) only prints the
ordered unit list: nothing is started or submitted.

Failure rules (as the former `grid.sh` behaved): a failed point prints
`FAILED <point>`, its later stages are skipped, the other points finish,
`validate` and the summary still run, and the exit status is non-zero.  A failed
once-only stage aborts before any point starts.  `--resume` is passed per unit
as the manifest says, so a stopped grid picks up where it stopped.

stdlib only.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import importlib.util
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMPAIGNS = ("random-bound", "in-band-bound")
DEFAULT_JOBS = 2  # the shared worker's rule: never above 2 unprompted


@dataclass
class Unit:
    id: str
    argv: list            # full command line
    cwd: Path
    point: str | None = None
    log: Path | None = None       # append stdout+stderr here
    stdout: Path | None = None    # overwrite with stdout (summary)
    after: tuple = ()             # must all have succeeded
    settle: tuple = ()            # must all have terminated
    is_run: bool = True           # a run.py call (takes --backend)
    stage: str = ""


def _load_points(campaign: str) -> list[str]:
    path = HERE / campaign / "run.py"
    sys.path.insert(0, str(path.parent))
    try:
        spec = importlib.util.spec_from_file_location(
            f"_pj_grid_{campaign.replace('-', '_')}_run", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(path.parent))
    return list(mod.load_points())


def load_manifest(campaign: str) -> dict:
    return json.loads((HERE / campaign / "grid.json").read_text())


def build_plan(campaign: str, points: list[str], manifest: dict | None = None,
               backend: str = "local", batch_apply: bool = False) -> list[Unit]:
    """The ordered unit list (plan order is depth-first per point)."""
    m = manifest or load_manifest(campaign)
    cwd = HERE / campaign
    run = [sys.executable, "run.py"]
    flags = ["--backend", backend] + (["--batch-apply"] if batch_apply else [])

    def run_argv(argv, resume, point=None):
        out = run + (["--resume"] if resume else [])
        if point:
            out += ["--point", point]
        return out + list(argv) + flags

    units: list[Unit] = []
    prev = None
    for o in m["once"]:
        units.append(Unit(o["id"], run_argv(o["argv"], o.get("resume", False)), cwd,
                          after=(prev,) if prev else (), stage=o["id"]))
        prev = o["id"]
    once_ids = tuple(u.id for u in units)
    point_ids = []
    for p in points:
        last = None
        for st in m["point_stages"]:
            uid = f"{st}:{p}"
            units.append(Unit(
                uid, run_argv(["--stage", st], m.get("point_resume", True), p), cwd,
                point=p, log=cwd / "logs" / f"grid_{p}.txt",
                after=(last,) if last else once_ids[-1:], stage=st))
            last = uid
        point_ids.append(last)
    ref = m["reference"]
    rid = f"{ref['id']}:{ref['point']}"
    units.append(Unit(
        rid, run_argv(["--stage", ref["id"]], ref.get("resume", False), ref["point"]),
        cwd, after=once_ids[-1:], settle=tuple(point_ids), stage=ref["id"]))
    s = m["summarize"]
    units.append(Unit("summarize", [sys.executable, s["script"]], cwd,
                      stdout=cwd / s["stdout"], after=once_ids[-1:],
                      settle=tuple(u.id for u in units if u.point or u.id == rid),
                      is_run=False, stage="summarize"))
    return units


def subprocess_executor(unit: Unit) -> int:
    env = dict(os.environ)
    # One thread per ngspice: parallel units must not each claim every core.
    env.setdefault("OMP_NUM_THREADS", "1")
    (unit.cwd / "logs").mkdir(parents=True, exist_ok=True)
    if unit.log:
        with open(unit.log, "a") as fh:
            return subprocess.call(unit.argv, cwd=unit.cwd, env=env,
                                   stdout=fh, stderr=subprocess.STDOUT)
    if unit.stdout:
        unit.stdout.parent.mkdir(parents=True, exist_ok=True)
        with open(unit.stdout, "w") as fh:
            return subprocess.call(unit.argv, cwd=unit.cwd, env=env, stdout=fh)
    return subprocess.call(unit.argv, cwd=unit.cwd, env=env)


def execute(units: list[Unit], executor, jobs: int, out=print) -> int:
    """Run the plan in dependency order; returns the process exit status."""
    state: dict[str, str] = {}   # id -> ok | failed | skipped
    pending = list(units)
    running: dict = {}
    failed_points: set = set()
    once_ids = {u.id for u in units if not u.point and u.is_run and u.stage != "validate"
                and not u.id.startswith("validate:")}
    abort = False

    def settled(i):
        return i in state

    with cf.ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        while pending or running:
            progressed = False
            for u in list(pending):
                if any(not settled(i) for i in u.after + u.settle):
                    continue
                if abort or any(state[i] != "ok" for i in u.after):
                    pending.remove(u)
                    state[u.id] = "skipped"
                    progressed = True
                    continue
                if len(running) >= jobs:
                    break              # plan order: nothing later jumps the queue
                pending.remove(u)
                running[pool.submit(executor, u)] = u
                progressed = True
            if running and not progressed:
                done, _ = cf.wait(running, return_when=cf.FIRST_COMPLETED)
                for fut in done:
                    u = running.pop(fut)
                    try:
                        rc = fut.result()
                    except Exception as exc:  # executor crash == failed unit
                        out(f"{u.id}: {exc}")
                        rc = 1
                    state[u.id] = "ok" if rc == 0 else "failed"
                    if rc != 0:
                        if u.point and u.point not in failed_points \
                                and u.stage != "validate":
                            failed_points.add(u.point)
                            out(f"FAILED {u.point}")
                        elif u.id in once_ids:
                            out(f"FAILED once-only stage {u.id}; aborting")
                            abort = True
            elif not running and not progressed and pending:
                raise RuntimeError("unsatisfiable dependencies: "
                                   + ", ".join(u.id for u in pending))
    return 0 if all(v == "ok" for v in state.values()) else 1


def print_plan(units: list[Unit], out=print) -> None:
    out(f"{len(units)} units, in plan order:")
    for n, u in enumerate(units, 1):
        dep = f"  after {','.join(u.after)}" if u.after else ""
        out(f"{n:4d}  {u.id}{dep}")


def main(argv=None, executor=None, points_provider=None, out=print) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("campaign", choices=CAMPAIGNS)
    ap.add_argument("--jobs", "-j", type=int, default=DEFAULT_JOBS)
    ap.add_argument("--backend", choices=("local", "batch"), default="local")
    ap.add_argument("--batch-apply", action="store_true",
                    help="with --backend batch, actually submit; otherwise a plan")
    ap.add_argument("--plan", action="store_true",
                    help="print the ordered unit list and exit; start nothing")
    a = ap.parse_args(argv)
    points = (points_provider or _load_points)(a.campaign)
    units = build_plan(a.campaign, points, backend=a.backend,
                       batch_apply=a.batch_apply)
    if a.plan or (a.backend == "batch" and not a.batch_apply):
        print_plan(units, out)
        if not a.plan:
            out("plan only: pass --batch-apply to submit.")
        return 0
    return execute(units, executor or subprocess_executor, a.jobs, out)


if __name__ == "__main__":
    sys.exit(main())
