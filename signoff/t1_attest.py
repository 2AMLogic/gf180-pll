#!/usr/bin/env python3
"""Artifact-anchored attestations for signoff T1 items 1, 9 and 10 (issue #798).

klt 0.7.0 accepts, for items 1, 2, 9 and 10, a `generic` envelope that declares
`t1_item`, names the audited artifact in `provenance.input.path` with its
content hash, and is pinned by the same hash in the block manifest.  This
script owns the audited artifacts (inventories under signoff/attest/) and the
envelopes beside them, and re-pins signoff/block-manifest.json.

Items 1 and 9 are attested per partition (`1.analog`, `1.digital`, `9.analog`,
`9.digital`); item 10 is a repository property and is cited once (`10`), which
the grader applies to both partitions.  Item 2 is deliberately not attested:
there is no block-level layout yet (#149).

The envelope `status` is an assertion, so this script derives it: every check
is evaluated mechanically against the working tree, and if any check fails
nothing is written (write mode) or the run fails (--check).  A pass means "the
inventory is complete, consistent and current", not "every result passes".

    python3 signoff/t1_attest.py            # (re)write inventories + envelopes, re-pin the manifest
    python3 signoff/t1_attest.py --check    # verify, write nothing (CI)

When `klt signoff --attest` ships in a released klayout-tools, switch to it
(klayout-tools#2844 closed, but the 0.7.0 wheel does not carry the flag).

Stdlib only; no simulator, PDK or network.  Exit: 0 ok, 1 --check drift,
2 a check failed or an input is missing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ATTEST = "signoff/attest"
MANIFEST = "signoff/block-manifest.json"
CI = ".github/workflows/ci.yml"
PARTITIONS = ("analog", "digital")

# --- item 1: which schematic belongs to which partition ----------------------
# design/README.md-adjacent boundary, recorded in signoff/README.md ("Block
# kind: mixed-signal") and DR-008.  Every design/*.sch must be listed here or
# in DESIGN_EXCLUDED, so a new schematic cannot silently escape the inventory.
DESIGN_DIGITAL = [
    "inv_3v3", "inv2x_3v3", "nand2_3v3", "nand3_3v3", "nor2_3v3", "tgate_3v3",
    "xor2_3v3", "schmitt_3v3", "delaywin_3v3", "dff_tg_3v3",
    "div23_cell", "divider_chain", "lock_detector",
]
DESIGN_ANALOG = [
    "vco", "vco_bias", "vco_stage",
    "pfd", "pfd_cp", "pfdcp_inv_3v3", "pfdcp_nand2_3v3", "srlatch", "edgedet",
    "cp", "cp_leg_n", "cp_leg_p", "cp_dumpbuf",
    "loop_filter", "pll_top",
]
DESIGN_EXCLUDED = {
    "dut_export": "scratch export root for `netlist.sh --top pfd_cp` (design/netlist.sh); not a block",
}
DESIGN_SHARED = ["design/xschemrc", "design/netlist.sh"]
GENERATORS = {"digital": ["design/gen_delaywin.py"], "analog": []}
# Committed netlists (design/netlist.sh BLOCKS) by partition.  pll_top is the
# assembled top and is carried by the analog partition; it instantiates the
# digital blocks, whose own netlists are listed on the digital side.
NETLISTS = {
    "digital": ["div23_cell", "divider_chain", "lock_detector", "dff_tg_3v3"],
    "analog": ["vco", "loop_filter", "pll_top"],
}
NETLIST_SUBCKT = {
    "div23_cell": "div23_cell", "divider_chain": "divider_chain",
    "lock_detector": "lock_detector", "dff_tg_3v3": "dff_tg_3v3",
    "vco": "vco", "loop_filter": "loop_filter", "pll_top": "pll_top",
}

# --- item 9: which experiment belongs to which partition ---------------------
# An experiment is a sim/<slug>/ directory with records/ (a claimed measurement).
# Digital: the divider and lock-detector campaigns.  Analog: everything else,
# including the closed-loop `pll_top` campaigns, whose behaviour is dominated by
# the VCO / charge pump / loop filter.
EXP_DIGITAL = [
    "divider-ratio", "divider-ratio-cell", "divider-ratio-chain",
    "divider-ratio-dff", "lock-detector", "lock-window-bisection",
    "lock-window-proxy", "lock-window-sizing", "lock-window-trim",
]
EXP_EXCLUDED = {
    "harness-selftest": "the harness's own acceptance bench; no design claim (sim/CHARACTERIZATION.md)",
}


class AttestError(Exception):
    pass


def sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def read(root: Path, rel: str) -> bytes:
    p = root / rel
    if not p.is_file():
        raise AttestError(f"missing file: {rel}")
    return p.read_bytes()


def entry(root: Path, rel: str, role: str) -> dict:
    return {"path": rel, "role": role, "content_hash": sha(read(root, rel))}


def dump(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def ci_text(root: Path) -> str:
    return read(root, CI).decode()


def pinned_pdk(root: Path) -> str:
    m = re.search(r"volare\"? enable --pdk gf180mcu ([0-9a-f]{40})", ci_text(root))
    if not m:
        raise AttestError(f"{CI}: no 'volare enable --pdk gf180mcu <rev>' pin")
    return m.group(1)


# --------------------------------------------------------------- item 1 ----
def design_sources(root: Path, part: str) -> dict:
    listed = set(DESIGN_DIGITAL) | set(DESIGN_ANALOG) | set(DESIGN_EXCLUDED)
    if set(DESIGN_DIGITAL) & set(DESIGN_ANALOG):
        raise AttestError("a schematic is assigned to both partitions")
    on_disk = {p.stem for p in (root / "design").glob("*.sch")}
    if on_disk - listed:
        raise AttestError(f"design/*.sch not assigned to a partition: {sorted(on_disk - listed)}")
    if listed - on_disk:
        raise AttestError(f"partition list names missing schematics: {sorted(listed - on_disk)}")
    names = DESIGN_DIGITAL if part == "digital" else DESIGN_ANALOG
    files = []
    for n in names:
        files.append(entry(root, f"design/{n}.sch", "source"))
        files.append(entry(root, f"design/{n}.sym", "source-symbol"))
    for rel in DESIGN_SHARED + GENERATORS[part]:
        files.append(entry(root, rel, "source-support"))
    for n in NETLISTS[part]:
        rel = f"design/netlist/{n}.spice"
        text = read(root, rel).decode()
        if not re.search(rf"(?m)^\.subckt\s+{re.escape(NETLIST_SUBCKT[n])}\b", text):
            raise AttestError(f"{rel}: no .subckt {NETLIST_SUBCKT[n]}")
        if len(re.findall(r"(?m)^[xXmM]", text)) < 3:
            raise AttestError(f"{rel}: fewer than 3 device instances (empty export?)")
        files.append(entry(root, rel, "derived-netlist"))
    ci = ci_text(root)
    if not re.search(r"(?m)^\s+run: \./design/netlist\.sh --check\s*$", ci):
        raise AttestError(f"{CI} no longer runs './design/netlist.sh --check'")
    nl = read(root, "design/netlist.sh").decode()
    for n in NETLISTS[part]:
        if n not in re.search(r"(?m)^BLOCKS=\(([^)]*)\)", nl).group(1).split():
            raise AttestError(f"design/netlist.sh BLOCKS does not export {n}")
    note = ("pfd_cp is exported per evidence record, not committed (design/netlist.sh); its "
            "freshness is carried by the sim/*/netlist-snapshots/ records, not by this inventory"
            ) if part == "analog" else None
    return {
        "schema_version": 1,
        "t1_item": 1,
        "partition": part,
        "subject": f"{part} design-source inventory",
        "full_custom_note": ("the digital partition is full-custom (DR-008): no RTL, so its item 1 is the "
                             "Analog column's artifact, schematic plus derived netlist"
                             if part == "digital" else None),
        "files": files,
        "regenerate": "./design/netlist.sh",
        "freshness_gate": {
            "command": "./design/netlist.sh --check",
            "run_by": f"{CI} (pdk-checks job, pinned xschem 3.4.7)",
            "what": "re-exports every committed top and diffs against design/netlist/*.spice",
        },
        **({"uncommitted_export": note} if note else {}),
        "excluded_schematics": DESIGN_EXCLUDED if part == "analog" else {},
        "checks": [
            "every design/*.sch is assigned to exactly one partition or explicitly excluded",
            "every listed schematic, symbol, support file and derived netlist exists",
            "each derived netlist declares its top subcircuit and has at least 3 device instances",
            "design/netlist.sh BLOCKS exports each listed netlist and CI runs 'design/netlist.sh --check'",
        ],
    }


# --------------------------------------------------------------- item 9 ----
def experiments(root: Path) -> list[str]:
    return sorted(p.parent.name for p in (root / "sim").glob("*/records") if p.is_dir())


def testbench_inventory(root: Path, part: str) -> dict:
    exps = experiments(root)
    if set(EXP_DIGITAL) - set(exps):
        raise AttestError(f"EXP_DIGITAL names experiments without records/: {sorted(set(EXP_DIGITAL) - set(exps))}")
    mine = [e for e in exps if e not in EXP_EXCLUDED and (e in EXP_DIGITAL) == (part == "digital")]
    charz = read(root, "sim/CHARACTERIZATION.md").decode()
    entries = []
    for e in mine:
        if f"`{e}`" not in charz:
            raise AttestError(f"sim/CHARACTERIZATION.md does not disclose experiment {e}")
        tbdirs = sorted(p for p in (root / "sim" / e).glob("testbench*") if p.is_dir())
        files = sorted(f for d in tbdirs for f in d.iterdir()
                       if f.is_file() and re.match(r"tb(_.*)?\.(sp|spice|json)$", f.name))
        if not any(f.suffix in (".sp", ".spice") for f in files):
            raise AttestError(f"sim/{e}: no committed tb_*.sp/.spice under testbench*/")
        if not list((root / "sim" / e / "records").glob("*.md")):
            raise AttestError(f"sim/{e}/records: no committed record")
        has_manifest = any(f.name == "tb.json" for f in files)
        runners = sorted(str(f.relative_to(root)) for d in tbdirs for f in d.glob("run*.sh"))
        if has_manifest:
            cold = f"python3 sim/run_corners.py {e}"
        elif runners:
            cold = runners[0]
        else:
            raise AttestError(f"sim/{e}: no tb.json manifest and no run*.sh driver")
        entries.append({
            "experiment": e,
            "testbenches": [{"path": str(f.relative_to(root)), "content_hash": sha(f.read_bytes())} for f in files],
            "cold_start": cold,
            "disclosed_in": "sim/CHARACTERIZATION.md",
        })
    rev = pinned_pdk(root)
    simreadme = read(root, "sim/README.md").decode()
    if rev not in simreadme:
        raise AttestError("sim/README.md does not cite the PDK revision CI pins")
    ci = ci_text(root)
    xs = re.search(r"XSCHEM_COMMIT: ([0-9a-f]{40})", ci)
    if not xs or "3.4.7" not in ci:
        raise AttestError(f"{CI}: xschem 3.4.7 / XSCHEM_COMMIT pin missing")
    klt = re.search(r"klayout-tools==([0-9][^'\"\s]*)", ci)
    if not klt:
        raise AttestError(f"{CI}: no klayout-tools pin")
    for p in ("sim/run_corners.py", "sim/selftest.sh", "sim/run-all.sh", "sim/pdk.json"):
        read(root, p)
    if not re.search(r"(?m)^\s+run: bash sim/selftest\.sh\s*$", ci):
        raise AttestError(f"{CI} no longer runs 'bash sim/selftest.sh'")
    return {
        "schema_version": 1,
        "t1_item": 9,
        "partition": part,
        "subject": f"{part} testbench inventory",
        "scope": "every sim/<slug>/ campaign with a committed record (a claimed measurement) "
                 "assigned to this partition; closed-loop pll_top campaigns are carried by analog",
        "excluded_experiments": EXP_EXCLUDED if part == "analog" else {},
        "pinned_pdk": {
            "open_pdks_revision": rev,
            "variant": json.loads(read(root, "sim/pdk.json"))["variant"],
            "pinned_in": [f"{CI} (volare enable)", "sim/README.md"],
        },
        "tool_versions": {
            "xschem": {"version": "3.4.7", "commit": xs.group(1), "pinned_in": CI},
            "klt": {"version": klt.group(1), "pinned_in": CI},
            "ngspice": {"pinned": False,
                        "note": "CI installs apt's ngspice; each evidence record states the version it ran on"},
        },
        "cold_start": {
            "prerequisites": "sim/README.md",
            "harness_campaigns": "python3 sim/run_corners.py <slug>",
            "smoke": "bash sim/selftest.sh",
        },
        "experiments": entries,
        "checks": [
            "every experiment with records/ is assigned to a partition or explicitly excluded",
            "each listed experiment is disclosed in sim/CHARACTERIZATION.md and has a committed record",
            "each has committed tb_*.sp/.spice testbenches and a tb.json manifest or a run*.sh driver",
            "sim/README.md cites the PDK revision CI installs; xschem and klt pins exist in CI",
            "CI runs 'bash sim/selftest.sh'",
        ],
    }


# -------------------------------------------------------------- item 10 ----
def repo_hygiene(root: Path, part: str | None) -> dict:
    readme = read(root, "README.md").decode()
    if not re.match(r"# gf180-pll\n\n\S", readme):
        raise AttestError("README.md does not open by stating what the block is")
    if not re.search(r"(?m)^## License\b", readme):
        raise AttestError("README.md lacks a '## License' section")
    contrib = read(root, "CONTRIBUTING.md").decode()
    if "From clone to a green self-test" not in contrib:
        raise AttestError("CONTRIBUTING.md lacks the 'From clone to a green self-test' section")
    lic = read(root, "LICENSE")
    if b"Apache License" not in lic:
        raise AttestError("LICENSE is not the Apache License text")
    read(root, "spec/pll.md")
    ci = ci_text(root)
    cmds = ["bash sim/selftest.sh", "./design/netlist.sh --check", "bash signoff/run-signoff.sh --check",
            "python3 signoff/t1_attest.py --check"]
    for c in cmds:
        if c not in ci:
            raise AttestError(f"{CI} no longer runs '{c}'")
    return {
        "schema_version": 1,
        "t1_item": 10,
        "subject": "repo-hygiene audit record",
        "readme": {
            "path": "README.md",
            "audited": ["opens with a block description", "## License section"],
            "hash_note": "README.md is edited often and is deliberately not hash-pinned; "
                         "t1_attest.py --check re-audits it in CI",
        },
        "contributing": {"path": "CONTRIBUTING.md", "audited": ["From clone to a green self-test"]},
        "spec": {"path": "spec/pll.md"},
        "license": {"path": "LICENSE", "kind": "Apache-2.0", "content_hash": sha(lic)},
        "ci": {
            "workflow": CI,
            "hash_note": "edited often; not hash-pinned. The commands below are re-audited by --check.",
            "required_commands": cmds,
        },
        "checks": [
            "README opens with a block description and has a License section",
            "CONTRIBUTING.md carries the clone-to-green-self-test section",
            "LICENSE is the Apache License text and spec/pll.md exists",
            "the CI workflow still runs each required command",
        ],
    }


# ------------------------------------------------------------------- glue ----
def cases(root: Path):
    """(manifest key, slug, item, summary, inventory dict)"""
    for part in PARTITIONS:
        yield (f"1.{part}", f"design-sources-{part}", 1,
               f"{part} partition: every design source and derived netlist inventoried; "
               "netlists regenerated and checked in CI",
               design_sources(root, part))
    for part in PARTITIONS:
        yield (f"9.{part}", f"testbench-inventory-{part}", 9,
               f"{part} partition: every claimed measurement's testbench committed with a cold-start "
               "command; PDK revision and tool pins recorded",
               testbench_inventory(root, part))
    yield ("10", "repo-hygiene", 10,
           "README, contributing guide, license, spec and the CI commands audited",
           repo_hygiene(root, None))


def outputs(root: Path):
    files: dict[str, str] = {}
    pins: dict[str, dict] = {}
    for key, slug, item, summary, inv in cases(root):
        inv_text = dump(inv)
        inv_rel = f"{ATTEST}/{slug}.json"
        env_rel = f"{ATTEST}/item-{key}.evidence.json"
        files[inv_rel] = inv_text
        files[env_rel] = dump({
            "schema_version": 1,
            "kind": "generic",
            "status": "pass",
            "t1_item": item,
            "summary": summary,
            "source": inv_rel,
            "provenance": {
                "klt_version": None, "klayout_version": None, "pdk": None, "deck": None,
                "input": {"content_hash": sha(inv_text.encode()), "path": {"path": inv_rel, "scope": "repo"}},
            },
        })
        pins[key] = {"file": env_rel, "content_hash": sha(inv_text.encode())}
    return files, pins


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="verify only; write nothing")
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    args = ap.parse_args(argv)
    root = Path(args.root)
    try:
        files, pins = outputs(root)
        man = json.loads(read(root, MANIFEST))
    except AttestError as exc:
        print(f"t1_attest: check failed: {exc}", file=sys.stderr)
        return 2
    evidence = dict(man.get("evidence", {}))
    evidence.update(pins)
    man["evidence"] = dict(sorted(evidence.items(), key=lambda kv: (int(kv[0].split(".")[0]), kv[0])))
    if args.check:
        drift = [rel for rel, text in files.items()
                 if not (root / rel).is_file() or (root / rel).read_text() != text]
        if (root / MANIFEST).read_text() != dump(man):
            drift.append(f"{MANIFEST} (evidence pins)")
        if drift:
            print(f"t1_attest: stale (run `python3 signoff/t1_attest.py`, then "
                  f"`bash signoff/run-signoff.sh`):", file=sys.stderr)
            for d in drift:
                print(f"  {d}", file=sys.stderr)
            return 1
        print("t1_attest: attestations for items 1, 9, 10 are current")
        return 0
    (root / ATTEST).mkdir(parents=True, exist_ok=True)
    for rel, text in files.items():
        (root / rel).write_text(text)
    (root / MANIFEST).write_text(dump(man))
    print(f"t1_attest: wrote {len(files)} files and re-pinned {MANIFEST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
