"""Hand a run's raw output to the artifact writer (``--artifact-store``).

``sim/lib/artifact-put.sh`` stores the bytes in the fleet artifact store and
writes ``manifests/artifacts/<bench>-<record-id>.manifest.json``; git keeps only
that manifest. The writer fails closed, and so does this module: any nonzero
writer exit is returned to the caller, which must not publish a record.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

PUT_SCRIPT = Path(__file__).resolve().parents[1] / "lib" / "artifact-put.sh"
STAGE_DIR = Path(__file__).resolve().parents[1] / ".artifact-stage"


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
    return 0
