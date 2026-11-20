"""Package and restore one mc-cp-mismatch record using its measured unit IDs."""

import csv
import gzip
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from fleet_batch import EXP, cached, expected_units, load, require, sha

WORK = EXP / "work"
REPO = EXP.parents[1]
BENCH = "mc-cp-mismatch"
SAMPLES = {"dc": "mc_cp_dc.csv", "sw": "mc_cp_switch.csv",
           "pfd": "mc_pfd_cp.csv", "dff": "mc_dff_ctq.csv"}


def record_tags(directory, samples):
    """Return log basenames for the rows actually reduced into this record."""
    tags = set()
    files = dict(SAMPLES) if samples else {}
    files["control"] = "negative_control.csv"
    for stage, name in files.items():
        with (directory / name).open() as stream:
            for row in csv.DictReader(line for line in stream if not line.startswith("#")):
                corner = row["corner"]
                if stage == "control":
                    tags.add(f"ctl_{row['stage']}_{corner}_{row['run']}")
                else:
                    base = f"{stage}_{corner}_seed{int(row['seed']):03}"
                    suffixes = ("_dm1n", "_d0", "_d1n") if stage == "pfd" else ("",)
                    tags.update(base + suffix for suffix in suffixes)
    require(all(re.fullmatch(r"[\w.\-]+", tag) for tag in tags), "invalid unit ID")
    return tags, files.values()


def members(directory, grid, rid):
    tags, csvs = record_tags(directory, grid != "control")
    expected = expected_units(WORK / "batch" / "control")
    if grid == "nominal":
        expected = {t: u for t, u in expected.items() if u["corner"] == "typical_27c_3.30v"}
    if grid != "control":
        expected.update(expected_units(WORK / "batch" / grid))
    require(tags == expected.keys(), f"{rid}: CSV rows and composed grid differ")
    for suffix, dut in [("cppfd", "dut.spice"), ("dff", "dut_dff.spice")]:
        snapshot = EXP / "netlist-snapshots" / f"{rid}-{suffix}.spice"
        require(snapshot.read_bytes() == (WORK / dut).read_bytes(), f"{dut} differs from snapshot")

    workers = {}
    receipts = {}
    for tag in sorted(tags):
        receipt = cached(WORK, tag, expected[tag])
        worker = receipt.pop("worker_environment")
        job = receipt["job_id"]
        require(workers.setdefault(job, worker) == worker, f"{job}: inconsistent worker stamps")
        receipts[tag] = receipt
        archived = directory / f"{tag}.log"
        log = (WORK / tag / "ngspice.log").read_bytes()
        if archived.exists():
            require(archived.read_bytes() == log, f"{rid}: {tag} differs from recorded output")
        yield f"{tag}.log", log
    for name in sorted(csvs):
        yield name, (directory / name).read_bytes()
    yield "fleet.json", json.dumps({"jobs": workers, "units": receipts}, sort_keys=True).encode()


def manifest(rid):
    return REPO / "manifests" / "artifacts" / f"{BENCH}-{rid}.manifest.json"


def publish(directory, grid, rid):
    # Stable metadata makes retries produce the same content-addressed object.
    with tempfile.TemporaryDirectory(dir=WORK) as scratch:
        archive = Path(scratch) / f"{rid}.tar.gz"
        with (
            archive.open("wb") as raw,
            gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as gz,
            tarfile.open(mode="w|", fileobj=gz) as tar,
        ):
            for name, data in members(directory, grid, rid):
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
        path = manifest(rid)
        if path.exists():
            require([entry["sha256"] for entry in load(path)["entries"]] == [sha(archive.read_bytes())],
                    f"{rid}: existing manifest describes different evidence")
        else:
            subprocess.run([str(REPO / "sim/lib/artifact-put.sh"), BENCH, rid, archive.name],
                           cwd=scratch, check=True)
        subprocess.run(["klt", "artifact", "verify", str(path)], cwd=REPO, check=True)


def restore(rid, directory):
    entry, = load(manifest(rid))["entries"]
    directory.mkdir(exist_ok=True, parents=True)
    require(not any(directory.iterdir()), f"restore needs an empty directory: {directory}")
    with tempfile.TemporaryDirectory() as scratch:
        archive = Path(scratch) / "evidence.tar.gz"
        subprocess.run(["klt", "artifact", "get", entry["sha256"], "-o", str(archive)], cwd=REPO, check=True)
        require(sha(archive.read_bytes()) == entry["sha256"], "downloaded archive checksum differs")
        with tarfile.open(archive) as tar:
            for member in tar:
                require(member.isfile() and re.fullmatch(r"[\w.-]+\.(csv|log|json)", member.name),
                        f"invalid evidence file {member.name}")
                with (directory / member.name).open("xb") as dest:
                    shutil.copyfileobj(tar.extractfile(member), dest)


def main(args):
    action, directory, *rest = args
    directory = Path(directory)
    if action == "local-logs":
        # Called after the CSVs and the shared control writer have completed.
        tags, _ = record_tags(directory, True)
        for tag in tags:
            if not tag.startswith("ctl_"):
                shutil.copyfile(WORK / tag / "ngspice.log", directory / f"{tag}.log")
        return
    rid = rest[-1]
    require(re.fullmatch(r"\d{8}-\d{6}-[a-f0-9]{7}", rid), "invalid record ID")
    if action == "restore":
        restore(rid, directory)
    elif action == "publish" and rest[0] in ("control", "full", "nominal"):
        publish(directory, rest[0], rid)
    else:
        raise ValueError(f"unknown operation {args}")


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except (TypeError, KeyError, ValueError, OSError, subprocess.CalledProcessError) as exc:
        sys.exit(f"fleet archive: {exc}")
