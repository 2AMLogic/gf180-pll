#!/usr/bin/env python3
"""Grade manifests/artifacts/*.manifest.json (issue #830).

Raw run output lives in the fleet artifact store; git keeps only a manifest
naming each object by sha256. This check is headless (no broker, no klt) and
fails when:

1. a manifest is not ``{schema_version: 1, entries: [...]}`` or an entry does
   not carry exactly the documented fields with the documented types;
2. an entry ``uri`` does not start with ``artifact:`` (so no ``s3://``,
   ``file://`` or ``https://`` location can be committed), or its key does not
   end in the entry's own sha256;
3. a stored object's bytes are also committed: some git-tracked file outside
   ``manifests/`` has a sha256 equal to an entry's.

Usage: sim/lib/check_artifact_manifests.py [--repo-root DIR]
Exit codes: 0 clean (also when there are no manifests), 1 any violation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

MANIFEST_DIR = "manifests/artifacts"
SCHEMA_VERSION = 1
REQUIRED = ("sha256", "size", "kind", "producer", "uri")
OPTIONAL = ("name", "media_type")
PRODUCER_FIELDS = {"tool", "version", "loom.repo", "commit"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
URI_PREFIX = "artifact:"


def entry_problems(entry) -> list[str]:
    if not isinstance(entry, dict):
        return ["entry is not an object"]
    problems = []
    missing = [f for f in REQUIRED if f not in entry]
    extra = sorted(set(entry) - set(REQUIRED) - set(OPTIONAL))
    if missing:
        problems.append(f"missing {', '.join(missing)}")
    if extra:
        problems.append(f"unknown field(s) {', '.join(extra)}")
    sha = entry.get("sha256")
    if not isinstance(sha, str) or not SHA256_RE.match(sha):
        problems.append("sha256 must be 64 lowercase hex digits")
    size = entry.get("size")
    if not isinstance(size, int) or isinstance(size, bool) or size < 1:
        problems.append("size must be a positive integer")
    if entry.get("kind") != "evidence":
        problems.append("kind must be 'evidence'")
    producer = entry.get("producer")
    if not isinstance(producer, dict) or set(producer) != PRODUCER_FIELDS:
        problems.append(f"producer must carry exactly {', '.join(sorted(PRODUCER_FIELDS))}")
    uri = entry.get("uri")
    if not isinstance(uri, str) or not uri.startswith(URI_PREFIX):
        problems.append(f"uri must start with {URI_PREFIX!r}")
    elif not uri[len(URI_PREFIX):] or uri.rsplit("/", 1)[-1] != sha:
        problems.append("uri key must be non-empty and end in the entry's sha256")
    for name in OPTIONAL:
        if name in entry and not isinstance(entry[name], str):
            problems.append(f"{name} must be a string")
    return problems


def load_manifest(path: Path):
    """(entries, problems) for one manifest file."""
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        return [], [f"unreadable JSON: {exc}"]
    if (
        not isinstance(data, dict)
        or data.get("schema_version") != SCHEMA_VERSION
        or not isinstance(data.get("entries"), list)
        or set(data) != {"schema_version", "entries"}
    ):
        return [], ["not {schema_version: 1, entries: [...]}"]
    problems = []
    for i, entry in enumerate(data["entries"]):
        problems += [f"entries[{i}]: {p}" for p in entry_problems(entry)]
    return data["entries"], problems


def tracked_files(root: Path) -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True
    ).stdout
    return [root / p for p in out.decode().split("\0") if p]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check(root: Path) -> list[str]:
    failures = []
    stored: dict[str, tuple[int, str]] = {}
    for path in sorted((root / MANIFEST_DIR).glob("*.manifest.json")):
        rel = path.relative_to(root)
        entries, problems = load_manifest(path)
        failures += [f"{rel}: {p}" for p in problems]
        for entry in entries:
            if not entry_problems(entry):
                stored[entry["sha256"]] = (entry["size"], str(rel))
    if not stored:
        return failures
    sizes = {size for size, _ in stored.values()}
    for path in tracked_files(root):
        rel = path.relative_to(root)
        if rel.parts[0] == "manifests" or not path.is_file() or path.is_symlink():
            continue
        if path.stat().st_size not in sizes:
            continue
        digest = sha256_file(path)
        if digest in stored:
            failures.append(
                f"{rel}: committed bytes equal a stored object "
                f"({digest[:12]}, listed in {stored[digest][1]})"
            )
    return failures


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    root = ap.parse_args(argv).repo_root.resolve()
    failures = check(root)
    for f in failures:
        print(f"FAIL: {f}", file=sys.stderr)
    n = len(list((root / MANIFEST_DIR).glob("*.manifest.json")))
    if failures:
        return 1
    print(f"OK: {n} artifact manifest(s) clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
