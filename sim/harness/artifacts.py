"""Hand a run's raw output to the artifact writer (``--artifact-store``).

``sim/lib/artifact-put.sh`` stores the bytes in the fleet artifact store and
writes ``manifests/artifacts/<bench>-<record-id>.manifest.json``; git keeps only
that manifest. The writer fails closed, and so does this module: any nonzero
writer exit is returned to the caller, which must not publish a record.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

PUT_SCRIPT = Path(__file__).resolve().parents[1] / "lib" / "artifact-put.sh"
STAGE_DIR = Path(__file__).resolve().parents[1] / ".artifact-stage"
REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = REPO_ROOT / "manifests" / "artifacts"

#: The per-point upload namespace (#1048): a completed point's logs are stored
#: under the staged name ``sim/.artifact-stage/<bench>-perpoint/<grid
#: fingerprint>/<corner-id>/<run-id>.log`` -- the manifest entry's ``name`` is
#: what a later run scans for, so the grid fingerprint and corner id travel
#: with the bytes. The per-point manifest itself is
#: ``manifests/artifacts/<bench>-perpoint-<record-id>.manifest.json``, one per
#: attempt, so concurrent attempts never race on one file and an attempt's
#: record id doubles as the adoption source.
PERPOINT_STEM = "perpoint"

#: One put at a time, process-wide: ``klt artifact put --manifest`` merges into
#: its manifest file, and ``run_grid``'s worker threads report concurrently.
_UPLOAD_LOCK = threading.Lock()


class ArtifactUploadError(RuntimeError):
    """Storing a point's raw output in the artifact store failed (#1048).

    The harness's artifact path fails closed: the caller must stop the run
    and must not publish a summary record over incomplete evidence.
    """


def raw_output_files(log_dir: Path, results, tb, raw_measures_path: Path) -> list[Path]:
    """Raw bytes a run left in ``log_dir``: per-corner logs, the raw-measures
    table and retained raw files. Derived tables are not raw output."""
    files = set(log_dir.glob("*.log"))
    files.add(raw_measures_path)
    for spec in tb.raw_files:
        if not spec.retain:
            continue
        for result in results:
            raw = result.raw_files.get(spec.name)
            if raw is not None and raw.exists():
                files.add(Path(raw.path))
    return sorted(p for p in files if p.is_file())


def store(bench: str, record_id: str, files: list[Path], put_script: Path | None = None) -> int:
    """Stage ``files`` and call the writer once. Returns the writer's exit code.

    On success the stored files are removed from their evidence directory so
    ``git add`` cannot pick them up; on failure nothing is removed.
    """
    if not files:
        print("error: --artifact-store: the run produced no raw output to store", file=sys.stderr)
        return 1
    script = put_script or PUT_SCRIPT
    stage = STAGE_DIR / f"{bench}-{record_id}"
    stage.mkdir(parents=True, exist_ok=True)
    staged = []
    for src in files:
        dst = stage / src.name
        if dst.exists():
            print(f"error: --artifact-store: duplicate raw file name {src.name}", file=sys.stderr)
            return 1
        shutil.copy2(src, dst)
        staged.append(dst)
    proc = subprocess.run(
        [str(script), bench, record_id, *map(str, staged)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=os.environ,
    )
    if proc.stdout:
        print(proc.stdout, end="" if proc.stdout.endswith("\n") else "\n")
    if proc.returncode != 0:
        if proc.stderr:
            print(proc.stderr, end="", file=sys.stderr)
        print(f"error: --artifact-store: writer exited {proc.returncode}; "
              "no summary record will be published", file=sys.stderr)
        return proc.returncode
    for src in files:
        src.unlink()
    # The staged copies are transient: the store holds the bytes and the
    # manifest names them, so nothing downstream reads them again -- the
    # per-point uploads already delete theirs. Leaving them would make a
    # second run that reserved the same id (same second, same commit, a
    # different checkout's experiment dir) collide with this run's leftovers
    # on its own stage directory and fail closed for no good reason (#1049).
    for dst in staged:
        dst.unlink(missing_ok=True)
    return 0


def manifest_path(bench: str, record_id: str, manifest_dir: Path | None = None) -> Path:
    """Where one run's end-of-run artifact manifest lives: the same default
    ``sim/lib/artifact-put.sh`` derives, exposed so the CLI's summary line
    and tests can name the file without re-deriving the layout."""
    return (manifest_dir or MANIFEST_DIR) / f"{bench}-{record_id}.manifest.json"


def require_store(purpose: str) -> None:
    """Fail closed before any work is spent on ``purpose`` (#1048).

    The store path has no fallback to committed bytes, so a run that will
    need the broker must find out before it dispatches a grid, not hours
    later at the first per-point upload. Raises :class:`ArtifactUploadError`
    when ``$KLT_ARTIFACT_BROKER`` is unset, ``klt`` is not on ``PATH``, or
    this klt lacks the ``artifact put``/``get`` subcommands the flow uses.
    """
    if not os.environ.get("KLT_ARTIFACT_BROKER"):
        raise ArtifactUploadError(
            f"KLT_ARTIFACT_BROKER is unset; {purpose} refuses "
            "(no fallback to committed bytes)"
        )
    for subcommand in ("put", "get"):
        try:
            proc = subprocess.run(
                ["klt", "artifact", subcommand, "--help"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=os.environ,
            )
        except OSError:
            # A klt binary that is not on PATH fails the same preflight as
            # one that lacks the subcommand: refused before dispatch, with
            # the reason stated -- not an unhandled traceback (#1049).
            raise ArtifactUploadError(
                f"klt not found on PATH; {purpose} refuses "
                "(no fallback to committed bytes)"
            ) from None
        if proc.returncode != 0:
            raise ArtifactUploadError(
                f"this klt has no 'artifact {subcommand}'; {purpose} refuses "
                "(no fallback to committed bytes)"
            )


def point_log_files(tb, corner_id: str, log_dir: Path) -> list[Path]:
    """One point's raw per-phase logs, in phase order (#1048).

    These are exactly the files ``replay_point`` reads back, so a point whose
    upload succeeded is adoptable by the next attempt, and a point that was
    never uploaded (failed, or killed mid-simulation) simply re-simulates.
    """
    return [log_dir / f"{phase.run_id(corner_id)}.log" for phase in tb.run_phases]


def store_point_logs(
    bench: str,
    record_id: str,
    fingerprint: str,
    corner_id: str,
    log_files: list[Path],
    put_script: Path | None = None,
    manifest_dir: Path | None = None,
) -> None:
    """Upload one completed point's raw logs as it finishes (#1048).

    The logs are staged under the per-point namespace -- ``name`` in the
    resulting manifest entries is what a later run's adoption scan matches
    on, so the staged path must carry the grid fingerprint and corner id --
    and ``klt artifact put`` merges the entries into this attempt's per-point
    manifest. Raises :class:`ArtifactUploadError` on any writer failure: the
    caller must stop the run and mint no record. The log files themselves
    stay in ``log_dir`` -- the end-of-run store publishes them under this
    record's own manifest, as it always has.
    """
    missing = [str(p) for p in log_files if not p.is_file()]
    if missing:
        raise ArtifactUploadError(
            f"point {corner_id} completed but its raw log(s) {', '.join(missing)} "
            "are missing -- refusing to store partial point evidence"
        )
    script = put_script or PUT_SCRIPT
    stage = STAGE_DIR / f"{bench}-{PERPOINT_STEM}" / fingerprint / corner_id
    stage.mkdir(parents=True, exist_ok=True)
    staged = []
    for src in log_files:
        dst = stage / src.name
        shutil.copy2(src, dst)
        staged.append(dst)
    manifest = (manifest_dir or MANIFEST_DIR) / f"{bench}-{PERPOINT_STEM}-{record_id}.manifest.json"
    with _UPLOAD_LOCK:
        proc = subprocess.run(
            [str(script), bench, f"{PERPOINT_STEM}-{record_id}",
             "--manifest", str(manifest), *map(str, staged)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=os.environ,
        )
    if proc.returncode != 0:
        message = proc.stderr.strip() or proc.stdout.strip()
        raise ArtifactUploadError(
            f"storing point {corner_id} failed (writer exit {proc.returncode})"
            + (f": {message}" if message else "")
        )
    for dst in staged:
        dst.unlink(missing_ok=True)


def lookup_stored_points(
    bench: str,
    fingerprint: str,
    manifest_dir: Path | None = None,
) -> tuple[dict[str, dict[str, str]], list[str]]:
    """Scan the manifests for this bench's stored points under one grid
    fingerprint (#1048).

    Returns ``({corner_id: {run-id: sha256}}, [source record ids])``. Only
    entries whose recorded ``name`` is the harness's per-point staging shape
    count -- any other entry is invisible to adoption, and a manifest that
    cannot be read as ``{schema_version, entries}`` is skipped outright: a
    malformed file must degrade the next attempt to re-simulation, never
    crash it. An entry name carrying a *different* fingerprint is invisible
    for the same reason a fetched byte mismatch is: adoption is keyed on a
    proven-identical grid, never a best-effort one.
    """
    directory = manifest_dir or MANIFEST_DIR
    stored: dict[str, dict[str, str]] = {}
    sources: list[str] = []
    prefix = f"{bench}-{PERPOINT_STEM}-"
    for manifest in sorted(directory.glob("*.manifest.json")):
        try:
            doc = json.loads(manifest.read_text())
            entries = doc["entries"]
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if not isinstance(entries, list):
            continue
        matched = False
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            sha = entry.get("sha256")
            if not isinstance(name, str) or not isinstance(sha, str):
                continue
            parts = name.split("/")
            for i, part in enumerate(parts):
                if part != f"{bench}-{PERPOINT_STEM}":
                    continue
                rest = parts[i + 1:]
                # <fingerprint>/<corner-id>/<run-id>.log
                if len(rest) != 3 or rest[0] != fingerprint:
                    break
                corner_id = rest[1]
                log_name = rest[2]
                if not log_name.endswith(".log"):
                    break
                stored.setdefault(corner_id, {})[log_name[:-len(".log")]] = sha
                matched = True
                break
        if matched:
            stem = manifest.name[: -len(".manifest.json")]
            sources.append(stem[len(prefix):] if stem.startswith(prefix) else stem)
    return stored, sources


def fetch_stored_log(sha256: str, dest: Path) -> bool:
    """Fetch one stored log and re-verify its bytes against the manifest
    entry's sha256 (#1048).

    ``klt artifact get`` already refuses to write bytes that do not hash to
    the requested object; the second hash here states the harness's own
    adoption contract and keeps it testable without depending on klt's
    internals. Any other outcome -- broker unreachable, object gone, a
    digest mismatch, an unreadable result -- returns ``False`` and removes
    whatever was written: the caller re-simulates that point, never mixing
    an unverified object into the record.
    """
    verified = False
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(
            ["klt", "artifact", "get", sha256, "-o", str(dest), "--force"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            cwd=REPO_ROOT, env=os.environ,
        )
        if proc.returncode == 0:
            verified = hashlib.sha256(dest.read_bytes()).hexdigest() == sha256
        return verified
    except OSError:
        return False
    finally:
        if not verified:
            try:
                dest.unlink()
            except OSError:
                pass
