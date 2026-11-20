"""Validate mc-cp-mismatch deck-list inputs, submission receipts and collected logs."""

import csv
import hashlib
import json
import math
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
PDK = json.loads((EXP.parent / "pdk.json").read_text())
ENGINE = "47"
METRICS = {
    "dc": {f"MCDC_{v}": ["iup", "idn"] for v in ("LO", "MID", "HI")},
    "sw": {"MCSW": ["iup_ss", "idn_ss", "qup", "qdn", "wup", "wdn", "wskew"]},
    "pfd": {"MCPFD": ["qnet"]},
    "dff": {"tcq_r": ["tcq_r"], "tcq_f": ["tcq_f"]},
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load(path):
    return json.loads(path.read_text())


def save(path, value):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, sort_keys=True, indent=1) + "\n")
    tmp.replace(path)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_log(data, stage):
    text = data.decode("utf-8", errors="replace")
    for marker, fields in METRICS[stage.removeprefix("ctl_")].items():
        rows = re.findall(rf"^{marker}\s+[^\n]*", text, re.MULTILINE)
        require(rows, f"missing {marker}")
        for field in fields:
            value = re.search(rf"\b{field}\s*=\s*(\S+)", rows[-1])
            require(value and math.isfinite(float(value[1])), f"invalid {field}")


def expected_units(batch):
    decks = batch / "decks"
    work = batch.parent.parent
    units = {}
    includes = {}
    with (batch / "units.tsv").open() as stream:
        for tag, stage, corner, timeout, deck in csv.reader(stream, delimiter="\t"):
            if deck not in includes:
                names = [deck] if deck == "dut_dff.spice" else [deck, "dut.spice"]
                includes[deck] = {}
                for name in names:
                    source = work / name if name.startswith("dut") else HERE / name
                    digest = sha(source.read_bytes())
                    require(sha((decks / name).read_bytes()) == digest,
                            f"{name} changed since compose")
                    includes[deck][name] = digest
            require(tag not in units, f"duplicate unit {tag}")
            units[tag] = {"stage": stage, "corner": corner,
                          "key": {"deck": f"{tag}.spice", "engine": "ngspice",
                                  "deck_sha256": sha((decks / f"{tag}.spice").read_bytes()),
                                  "inputs": {}, "includes": includes[deck], "outputs": [],
                                  "timeout_s": int(timeout), "engine_version": ENGINE}}
    require(units, f"empty expected grid in {batch}; compose first")
    return units


def check_worker(worker):
    pdk = worker["pdk"]
    require(worker["capture"] == "ok" and pdk["variant"] == PDK["variant"]
            and pdk["stamp_scope"] == "executed"
            and ["open_pdks", PDK["open_pdks"]] in [s.split() for s in pdk["stamp_text"].splitlines()],
            "worker PDK differs from sim/pdk.json or lacks an executed stamp")
    require(worker["simulator"]["version_probe"] == "ok"
            and re.search(rf"\bngspice-{ENGINE}\b", worker["simulator"]["version_banner"]),
            f"worker simulator differs from ngspice-{ENGINE}")


def check_unit(tag, unit, receipt, data):
    require(receipt["id"] == tag and receipt["key"] == unit["key"],
            f"{tag}: deck/DUT or simulator differs")
    require(bool(receipt["job_id"]) and receipt["stdout_sha256"] == sha(data),
            f"{tag}: missing fleet job or changed stdout")
    check_worker(receipt["worker_environment"])
    check_log(data, unit["stage"])


def cached(work, tag, unit):
    directory = work / tag
    receipt = load(directory / "fleet.json")
    check_unit(tag, unit, receipt, (directory / "ngspice.log").read_bytes())
    return receipt


def request_name(request, units):
    keys = [units[d["id"]]["key"] for d in request["decks"]]
    fingerprint = sha(json.dumps([request, keys], sort_keys=True).encode())
    return f"request-{fingerprint}.json"


def compose(batch, units, jobs):
    work = batch.parent.parent
    pending = {}
    for tag, unit in units.items():
        try:
            cached(work, tag, unit)
        except (OSError, ValueError, KeyError, TypeError):
            pending[tag] = unit
    count = len(pending)
    active = []
    # Re-attach an accepted, partially collected request after interruption.
    for name in jobs:
        request = load(batch / name)
        tags = [d["id"] for d in request["decks"]]
        if (all(tag in units for tag in tags) and any(tag in pending for tag in tags)
                and request_name(request, units) == name):
            active.append(name)
            for tag in tags:
                pending.pop(tag, None)
    by_corner = defaultdict(list)
    for tag, unit in pending.items():
        by_corner[unit["corner"]].append({"id": tag, "deck": f"decks/{tag}.spice",
                                          "outputs": [], "timeout_s": unit["key"]["timeout_s"]})
    for decks in by_corner.values():
        request = {"backend": "batch", "models": {"pdk": PDK["variant"]}, "decks": decks,
                   "options": {"timeout_s": 1800},
                   "batch": {"capacity_wait_s": 600, "poll_timeout_s": 86400}}
        name = request_name(request, units)
        save(batch / name, request)
        active.append(name)
    save(batch / "requests.json", {
        "expected_sha256": sha((batch / "units.tsv").read_bytes()), "requests": active})
    print(f"{len(units)} expected units, {len(units) - count} verified cached, {count} pending")


def submit(batch, name, jobs):
    if name in jobs:
        return
    # klt writes this receipt immediately after launch, before returning to
    # us. Recover it if the parent was interrupted before saving its ledger.
    out = batch / Path(name).stem
    receipt = out / "batch-receipt.json"
    if receipt.exists():
        result = load(receipt)
    else:
        cmd = ["klt", "sim", str(batch / name), "--submit-only", "--wait-for-capacity", "600",
               "-o", str(out), "--format", "json"]
        print(f"Submitting {name}", flush=True)
        proc = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, text=True)
        if proc.returncode:
            sys.stderr.write(proc.stdout)
            raise ValueError(f"{name}: submit refused (exit {proc.returncode})")
        result = json.loads(proc.stdout)
    job_id = result["job_id"]
    require(isinstance(job_id, str) and re.fullmatch(r"[\w.-]+", job_id), "missing job ID")
    jobs[name] = job_id
    save(batch / "accepted.json", jobs)


def collect(batch, name, job_id, units):
    request = load(batch / name)
    out = batch / f"attached-{job_id}"
    cmd = ["klt", "sim", str(batch / name), "--attach", job_id, "-o", str(out),
           "--format", "json"]
    report = json.loads(subprocess.check_output(cmd))
    remote = report["environment"]["remote"]
    require(report["status"] == "pass" and report["backend"] == "batch"
            and remote["job_id"] == job_id, f"{job_id}: unexpected fleet report")
    worker = remote["worker_environment"]
    check_worker(worker)
    returned = {row["id"]: row for row in report["units"]}
    tags = [d["id"] for d in request["decks"]]
    require(set(tags) == returned.keys() and len(tags) == len(report["units"]),
            f"{job_id}: returned unit IDs differ from request")
    for tag in tags:
        record = load(out / tag / "unit.json")
        row = returned[tag]
        require(row == record["result"] and row["status"] == "pass"
                and row["exit_code"] == 0 and row["deck_sha256"] == units[tag]["key"]["deck_sha256"],
                f"{tag}: unsuccessful or mismatched completion record")
        data = (out / tag / "stdout.bin").read_bytes()
        receipt = {"id": tag, "job_id": job_id, "key": record["key"],
                   "worker_environment": worker, "stdout_sha256": sha(data)}
        check_unit(tag, units[tag], receipt, data)
        directory = batch.parent.parent / tag
        directory.mkdir(exist_ok=True)
        tmp = directory / "ngspice.log.tmp"
        tmp.write_bytes(data)
        tmp.replace(directory / "ngspice.log")
        save(directory / "fleet.json", receipt)


def main(action, batch):
    units = expected_units(batch)
    ledger = batch / "accepted.json"
    jobs = load(ledger) if ledger.exists() else {}
    if action == "compose":
        compose(batch, units, jobs)
        return
    plan = load(batch / "requests.json")
    require(plan["expected_sha256"] == sha((batch / "units.tsv").read_bytes()),
            "expected grid changed; compose first")
    if action == "verify":
        for tag, unit in units.items():
            cached(batch.parent.parent, tag, unit)
        print(f"verified all {len(units)} expected units")
    elif action == "simulator":
        tag = next(iter(units))
        receipt = cached(batch.parent.parent, tag, units[tag])
        print("ngspice-" + receipt["key"]["engine_version"])
    elif action == "recover":
        # Original two-column ledgers do not pin request contents. Only a
        # successful attach and worker input-key check can adopt those units.
        with (batch / "jobs.tsv").open() as stream:
            for name, job_id in csv.reader(stream, delimiter="\t"):
                collect(batch, name, job_id, units)
    elif action in ("submit", "collect", "status"):
        for name in plan["requests"]:
            require(request_name(load(batch / name), units) == name, f"{name}: recompose inputs")
            if action == "submit":
                submit(batch, name, jobs)
            elif action == "collect":
                collect(batch, name, jobs[name], units)
            else:
                subprocess.run(["klt", "sim", str(batch / name), "--job-status", jobs[name],
                                "--format", "json"], check=True)
    else:
        raise ValueError(f"unknown operation {action}")


if __name__ == "__main__":
    try:
        main(sys.argv[1], Path(sys.argv[2]))
    except (KeyError, TypeError, ValueError, OSError, subprocess.CalledProcessError) as exc:
        sys.exit(f"run_batch: {exc}")
