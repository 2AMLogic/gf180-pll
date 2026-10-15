"""The simulator init file both execution backends stage before the netlist is read.

``set wnflag=1`` changes how ngspice reads the netlist (it must be in place
*before* the deck is parsed -- setting it in the deck's own ``.control`` block
is too late), and with the closed-loop deck it moves the DC solution to a
different state. A backend that does not control the init file therefore
produces numbers that are not comparable with another backend's, whatever the
deck says. See ``sim/BATCH-IMAGE-DIAGNOSIS-2026-10-08.md`` (Addendums 3 to 7)
and DR-040.

The contract, shared by :class:`sim.harness.execution.LocalBackend` and
:class:`sim.harness.batch.BatchBackend`:

* the same bytes (:data:`INIT_TEXT`) are staged as ``.spiceinit`` in the
  directory ngspice is started from. ngspice reads a working-directory
  ``.spiceinit`` *instead of* ``~/.spiceinit``, so an ambient user or image
  init file is shadowed without touching ``HOME`` or any user file;
* the file echoes :data:`MARKER` as it runs, so the deck's own output carries
  proof that the initialization was executed -- a banner, or the file merely
  existing, is not that proof (:func:`init_of`).
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path

#: Name ngspice looks for in its working directory.
INIT_NAME = ".spiceinit"

#: Name the batch job uploads the bytes under. The job command copies it to
#: :data:`INIT_NAME` in the directory ngspice runs from; a non-dot name keeps
#: it visible to the flat-upload contract and to ``ls`` in a job log.
UPLOAD_NAME = "harness.spiceinit"

#: What ngspice prints from the init file when it actually ran it.
MARKER = "gf180-pll-spiceinit-applied"

INIT_TEXT = (
    "* gf180-pll harness simulator init (reference configuration, DR-040)\n"
    "set wnflag=1\n"
    f"echo {MARKER} wnflag=$wnflag\n"
)

INIT_SHA256 = hashlib.sha256(INIT_TEXT.encode()).hexdigest()

_APPLIED_RE = re.compile(rf"^{re.escape(MARKER)} wnflag=1\s*$", re.MULTILINE)


def init_of(output: str) -> str:
    """The init identity (``sha256:<hex>``) the deck's output proves ran, else ``""``.

    The identity is the checksum of the bytes this module stages; it is only
    reported when the simulator's own output shows the marker, so a run whose
    init file was absent, shadowed or not executed is unattributed rather than
    credited with a configuration it did not use.
    """
    return f"sha256:{INIT_SHA256}" if _APPLIED_RE.search(output or "") else ""


def stage(rundir: Path) -> Path:
    """Write :data:`INIT_TEXT` as ``.spiceinit`` in ``rundir``; return its path.

    Idempotent and safe for parallel phases that share a directory: identical
    bytes are left alone, otherwise the file is replaced atomically. Only this
    one job-owned file is touched.
    """
    target = Path(rundir) / INIT_NAME
    try:
        if target.read_text() == INIT_TEXT:
            return target
    except (OSError, UnicodeDecodeError):
        pass
    fd, tmp = tempfile.mkstemp(dir=rundir, prefix=".spiceinit.")
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(INIT_TEXT)
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return target
